import hashlib
from dataclasses import replace

import pytest
from qdrant_client import QdrantClient

from jmi.rag.index import Document, collection_name, sync
from jmi.rag.search import search

DIM = 16


class FakeEmbedder:
    """Deterministic bag-of-words vectors: shared words -> higher cosine. Counts calls."""

    def __init__(self):
        self.texts: list[str] = []

    def __call__(self, texts):
        self.texts.extend(texts)
        vectors = []
        for text in texts:
            vec = [0.0] * DIM
            for word in text.lower().split():
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
            vectors.append(vec if any(vec) else [1.0] + [0.0] * (DIM - 1))
        return vectors


def make_doc(vacancy_id: str, title: str, body: str, **overrides) -> Document:
    fields = dict(vacancy_id=vacancy_id, source="himalayas", source_id=f"acme/{vacancy_id}", title=title,
                  company="Acme", url=f"https://himalayas.app/companies/acme/jobs/{vacancy_id}",
                  seniority_level="senior", is_remote=True, country="", city="remote", salary_month_usd_mid=None,
                  skills=["Python"], published_date="2026-11-01", last_seen_dt="2026-11-01",
                  description_html=f"<h3>Requirements</h3><p>{body}</p>")
    return Document(**{**fields, **overrides})


@pytest.fixture
def qdrant():
    return QdrantClient(":memory:")


def test_first_sync_embeds_everything(qdrant):
    embed = FakeEmbedder()
    stats = sync(qdrant, [make_doc("1", "Data Engineer", "airflow dbt clickhouse"),
                          make_doc("2", "Frontend Developer", "react typescript css")], "sections", embed)
    assert stats["embedded"] == 2 and stats["chunks"] == 2
    assert qdrant.count(collection_name("sections")).count == 2


def test_resync_without_changes_embeds_nothing(qdrant):
    docs = [make_doc("1", "Data Engineer", "airflow dbt clickhouse")]
    sync(qdrant, docs, "window", FakeEmbedder())
    embed = FakeEmbedder()
    stats = sync(qdrant, docs, "window", embed)
    assert embed.texts == []
    assert stats["unchanged"] == 1


def test_metadata_change_updates_payload_without_embedding(qdrant):
    doc = make_doc("1", "Data Engineer", "airflow dbt clickhouse")
    sync(qdrant, [doc], "sections", FakeEmbedder())
    embed = FakeEmbedder()
    stats = sync(qdrant, [replace(doc, last_seen_dt="2026-11-05", salary_month_usd_mid=9000.0)], "sections", embed)
    assert embed.texts == [] and stats["retagged"] == 1
    payload = qdrant.scroll(collection_name("sections"), with_payload=True)[0][0].payload
    assert payload["last_seen_dt"] == "2026-11-05" and payload["salary_month_usd_mid"] == 9000.0


def test_text_change_replaces_old_chunks(qdrant):
    long_body = " ".join(f"word{i}" for i in range(800))
    doc = make_doc("1", "Data Engineer", long_body)
    sync(qdrant, [doc], "window", FakeEmbedder())
    assert qdrant.count(collection_name("window")).count == 3

    stats = sync(qdrant, [replace(doc, description_html="<p>now short</p>")], "window", FakeEmbedder())
    assert stats["embedded"] == 1
    assert qdrant.count(collection_name("window")).count == 1


def test_vacancies_gone_from_marts_are_deleted(qdrant):
    sync(qdrant, [make_doc("1", "A", "x y z"), make_doc("2", "B", "x y z")], "window", FakeEmbedder())
    stats = sync(qdrant, [make_doc("1", "A", "x y z")], "window", FakeEmbedder())
    assert stats["deleted"] == 1
    assert qdrant.count(collection_name("window")).count == 1


def test_embedded_text_has_contextual_header(qdrant):
    embed = FakeEmbedder()
    sync(qdrant, [make_doc("1", "Data Engineer", "airflow")], "sections", embed)
    # embed.texts[0] is the dimension probe of a fresh collection.
    assert embed.texts[1].startswith("Data Engineer at Acme (senior, remote)\nSection: Requirements")


def test_search_ranks_by_similarity_and_filters(qdrant):
    embed = FakeEmbedder()
    sync(qdrant, [make_doc("1", "Data Engineer", "airflow dbt clickhouse pipelines"),
                  make_doc("2", "Frontend Developer", "react typescript css", seniority_level="middle")],
         "sections", embed)
    hits = search(qdrant, embed, "airflow dbt clickhouse pipelines", strategy="sections", limit=2)
    assert hits[0].vacancy_id == "1"
    filtered = search(qdrant, embed, "airflow dbt", strategy="sections", seniority="middle")
    assert [h.vacancy_id for h in filtered] == ["2"]


def test_search_collapses_reposts_of_the_same_posting(qdrant):
    embed = FakeEmbedder()
    body = "airflow dbt clickhouse pipelines"
    sync(qdrant, [make_doc("1", "Data Engineer", body), make_doc("2", "Data Engineer", body),
                  make_doc("3", "Analytics Engineer", "dbt models and sql")], "sections", embed)
    hits = search(qdrant, embed, body, strategy="sections", limit=3)
    assert len(hits) == 2
    assert hits[0].vacancy_id in {"1", "2"} and hits[1].vacancy_id == "3"
