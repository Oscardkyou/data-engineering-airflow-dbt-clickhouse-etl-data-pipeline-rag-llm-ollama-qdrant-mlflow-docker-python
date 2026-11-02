"""Stage 5: keep the Qdrant vector index in sync with the marts.

Runs after every successful dbt build. Both chunking strategies are indexed so stage 7 can
compare their retrieval quality. Only new or changed vacancies are embedded.
"""

from datetime import datetime, timedelta

from airflow.sdk import dag, task

from jmi.alerts import on_task_failure
from jmi.assets import MARTS, VECTOR_INDEX
from jmi.rag.chunking import STRATEGIES


@dag(
    schedule=[MARTS],
    start_date=datetime(2026, 11, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2), "on_failure_callback": on_task_failure},
    tags=["rag"],
)
def rag_index():
    # One GPU behind Ollama: embedding two collections at once only makes both slower.
    @task(max_active_tis_per_dag=1, outlets=[VECTOR_INDEX])
    def sync_collection(strategy: str) -> dict:
        from qdrant_client import QdrantClient

        from jmi.clients import clickhouse_client
        from jmi.config import settings
        from jmi.rag.embeddings import OllamaEmbedder
        from jmi.rag.index import load_documents, sync

        docs = load_documents(clickhouse_client())
        return sync(QdrantClient(url=settings.qdrant_url, timeout=60), docs, strategy, OllamaEmbedder())

    sync_collection.expand(strategy=list(STRATEGIES))


rag_index()
