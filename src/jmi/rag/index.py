"""Incremental sync of vacancies from the marts into Qdrant.

Embedding is the expensive step, so each vacancy carries two hashes in its payload:

* ``doc_hash``  - what was embedded (text + chunking version). Changed -> re-chunk and re-embed.
* ``meta_hash`` - filterable metadata (last_seen_dt, salary, ...). Changed -> cheap payload update.

Vacancies that left the marts are deleted, so the index mirrors ``fct_vacancy``.
A daily run on unchanged data embeds nothing.
"""

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass

from qdrant_client import QdrantClient, models

from jmi.rag.chunking import Chunk, chunk
from jmi.rag.embeddings import Embedder

# Bump when chunking or the embedded text format changes: every document is then re-embedded.
CHUNKING_VERSION = "1"
UPSERT_BATCH = 64

DOCUMENTS_SQL = """
select
    toString(f.vacancy_key) as vacancy_id,
    f.source as source,
    f.source_id as source_id,
    f.title as title,
    ifNull(v.company, '') as company,
    f.url as url,
    f.seniority_level as seniority_level,
    f.is_remote as is_remote,
    ifNull(v.country, '') as country,
    ifNull(v.city, '') as city,
    f.salary_month_usd_mid as salary_month_usd_mid,
    v.skills as skills,
    toString(f.published_date) as published_date,
    toString(f.last_seen_dt) as last_seen_dt,
    v.description_html as description_html
from analytics.fct_vacancy as f
inner join analytics.int_vacancies_unified as v
    on v.source = f.source and v.source_id = f.source_id
"""

INDEXED_FIELDS = {
    "vacancy_id": models.PayloadSchemaType.KEYWORD,
    "source": models.PayloadSchemaType.KEYWORD,
    "seniority_level": models.PayloadSchemaType.KEYWORD,
    "section_kind": models.PayloadSchemaType.KEYWORD,
    "skills": models.PayloadSchemaType.KEYWORD,
    "is_remote": models.PayloadSchemaType.BOOL,
    "salary_month_usd_mid": models.PayloadSchemaType.FLOAT,
    "last_seen_dt": models.PayloadSchemaType.DATETIME,
}


@dataclass(frozen=True)
class Document:
    vacancy_id: str
    source: str
    source_id: str
    title: str
    company: str
    url: str
    seniority_level: str
    is_remote: bool
    country: str
    city: str
    salary_month_usd_mid: float | None
    skills: list[str]
    published_date: str
    last_seen_dt: str
    description_html: str

    def metadata(self) -> dict:
        meta = asdict(self)
        meta.pop("description_html")
        return meta

    @property
    def doc_hash(self) -> str:
        return _hash([CHUNKING_VERSION, self.title, self.company, self.seniority_level,
                      self.is_remote, self.city, self.description_html])

    @property
    def meta_hash(self) -> str:
        return _hash(self.metadata())


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def collection_name(strategy: str) -> str:
    return f"vacancies_{strategy}"


def point_id(vacancy_id: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"jmi:{vacancy_id}#{index}"))


def embedding_text(doc: Document, piece: Chunk) -> str:
    """Contextual header: a chunk like '5+ years of Python' is useless without knowing the job."""
    where = "remote" if doc.is_remote else (doc.city or doc.country or "location n/a")
    header = f"{doc.title} at {doc.company or 'unknown company'} ({doc.seniority_level}, {where})"
    if piece.section:
        header += f"\nSection: {piece.section}"
    return f"{header}\n{piece.text}".strip()


def load_documents(ch) -> list[Document]:
    result = ch.query(DOCUMENTS_SQL)
    return [Document(**dict(zip(result.column_names, row, strict=True))) for row in result.result_rows]


def ensure_collection(qdrant: QdrantClient, name: str, dim: int) -> None:
    if qdrant.collection_exists(name):
        return
    qdrant.create_collection(name, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
    for field, schema in INDEXED_FIELDS.items():
        qdrant.create_payload_index(name, field_name=field, field_schema=schema)


def _by_vacancy(vacancy_ids) -> models.Filter:
    return models.Filter(must=[models.FieldCondition(key="vacancy_id", match=models.MatchAny(any=list(vacancy_ids)))])


def indexed_hashes(qdrant: QdrantClient, name: str) -> dict[str, tuple[str, str]]:
    """vacancy_id -> (doc_hash, meta_hash), read from the payloads already in the collection."""
    found: dict[str, tuple[str, str]] = {}
    offset = None
    while True:
        points, offset = qdrant.scroll(name, limit=1000, offset=offset, with_vectors=False,
                                       with_payload=["vacancy_id", "doc_hash", "meta_hash"])
        for p in points:
            found[p.payload["vacancy_id"]] = (p.payload["doc_hash"], p.payload["meta_hash"])
        if offset is None:
            return found


def sync(qdrant: QdrantClient, docs: list[Document], strategy: str, embed: Embedder) -> dict:
    name = collection_name(strategy)
    if not qdrant.collection_exists(name):
        ensure_collection(qdrant, name, dim=len(embed(["dimension probe"])[0]))
    existing = indexed_hashes(qdrant, name)
    current = {d.vacancy_id: d for d in docs}

    stale = existing.keys() - current.keys()
    to_embed = [d for d in docs if existing.get(d.vacancy_id, ("",))[0] != d.doc_hash]
    to_retag = [d for d in docs if d.vacancy_id in existing
                and existing[d.vacancy_id][0] == d.doc_hash and existing[d.vacancy_id][1] != d.meta_hash]

    # Changed documents may now have fewer chunks: drop their old points before upserting.
    removed = stale | {d.vacancy_id for d in to_embed if d.vacancy_id in existing}
    if removed:
        qdrant.delete(name, points_selector=models.FilterSelector(filter=_by_vacancy(removed)))

    chunks_written = 0
    pending: list[tuple[str, str, dict]] = []
    for doc in to_embed:
        pieces = chunk(doc.description_html, strategy) or [Chunk(0, "")]
        for piece in pieces:
            payload = {**doc.metadata(), "doc_hash": doc.doc_hash, "meta_hash": doc.meta_hash,
                       "strategy": strategy, "chunk_index": piece.index, "section": piece.section,
                       "section_kind": piece.section_kind, "text": piece.text}
            pending.append((point_id(doc.vacancy_id, piece.index), embedding_text(doc, piece), payload))
        if len(pending) >= UPSERT_BATCH:
            chunks_written += _upsert(qdrant, name, pending, embed)
            pending = []
    chunks_written += _upsert(qdrant, name, pending, embed)

    for doc in to_retag:
        qdrant.set_payload(name, payload={**doc.metadata(), "meta_hash": doc.meta_hash},
                           points=_by_vacancy([doc.vacancy_id]))

    return {"collection": name, "documents": len(docs), "embedded": len(to_embed), "chunks": chunks_written,
            "retagged": len(to_retag), "deleted": len(stale), "unchanged": len(docs) - len(to_embed) - len(to_retag)}


def _upsert(qdrant: QdrantClient, name: str, pending: list[tuple[str, str, dict]], embed: Embedder) -> int:
    if not pending:
        return 0
    vectors = embed([text for _, text, _ in pending])
    qdrant.upsert(name, points=[
        models.PointStruct(id=pid, vector=vector, payload=payload)
        for (pid, _, payload), vector in zip(pending, vectors, strict=True)
    ])
    return len(pending)
