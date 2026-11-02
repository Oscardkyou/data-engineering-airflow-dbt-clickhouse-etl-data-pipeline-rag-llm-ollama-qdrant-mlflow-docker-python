"""Semantic search over the vacancy index, with optional structured filters."""

from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from jmi.rag.embeddings import Embedder
from jmi.rag.index import collection_name


@dataclass(frozen=True)
class Hit:
    score: float
    vacancy_id: str
    title: str
    company: str
    url: str
    section: str | None
    text: str
    payload: dict


def build_filter(*, seniority: str | None = None, remote: bool | None = None, source: str | None = None,
                 section_kind: str | None = None, skill: str | None = None,
                 min_salary_usd: float | None = None) -> models.Filter | None:
    must: list[models.Condition] = []
    for key, value in (("seniority_level", seniority), ("source", source),
                       ("section_kind", section_kind), ("skills", skill)):
        if value:
            must.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
    if remote is not None:
        must.append(models.FieldCondition(key="is_remote", match=models.MatchValue(value=remote)))
    if min_salary_usd is not None:
        must.append(models.FieldCondition(key="salary_month_usd_mid", range=models.Range(gte=min_salary_usd)))
    return models.Filter(must=must) if must else None


def search(qdrant: QdrantClient, embed: Embedder, query: str, *, strategy: str = "sections", limit: int = 5,
           one_per_vacancy: bool = True, **filters) -> list[Hit]:
    """Top chunks for the query. With one_per_vacancy, the best chunk of each distinct posting only.

    Distinct by doc_hash, not vacancy_id: some companies repost the same job under several URLs,
    and five copies of one posting would crowd out everything else.
    """
    vector = embed([query])[0]
    points = qdrant.query_points(
        collection_name(strategy), query=vector, query_filter=build_filter(**filters),
        limit=limit * 4 if one_per_vacancy else limit, with_payload=True,
    ).points

    hits: list[Hit] = []
    seen: set[str] = set()
    for p in points:
        posting = p.payload["doc_hash"]
        if one_per_vacancy and posting in seen:
            continue
        seen.add(posting)
        hits.append(Hit(p.score, p.payload["vacancy_id"], p.payload["title"], p.payload["company"], p.payload["url"],
                        p.payload.get("section"), p.payload["text"], p.payload))
        if len(hits) == limit:
            break
    return hits
