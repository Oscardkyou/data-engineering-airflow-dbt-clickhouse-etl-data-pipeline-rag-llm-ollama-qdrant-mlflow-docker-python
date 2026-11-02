# Job Market Insights

Daily pipeline that collects IT job postings (hh.ru, Remotive), lands them in an S3 data lake,
models them in ClickHouse with dbt, and serves a RAG assistant on top of a local LLM.

> Work in progress — built stage by stage. Full write-up comes in stage 8.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow 3 (LocalExecutor) |
| Data lake | SeaweedFS (S3 API) |
| DWH | ClickHouse |
| Transformations | dbt |
| Vector store | Qdrant |
| LLM / embeddings | Ollama on host (qwen3:30b, bge-m3) |
| Experiment tracking | MLflow (Postgres backend, artifacts in S3) |

## Run locally

Requires Docker Desktop (WSL2) and Ollama on the host with `bge-m3` and `qwen3:30b` pulled.

```bash
python scripts/make_env.py      # creates .env with random local secrets
docker compose up -d --build
docker compose exec airflow-scheduler airflow dags test infra_smoke
```

| Service | URL |
|---|---|
| Airflow | http://localhost:8080 |
| MLflow | http://localhost:5000 |
| S3 filer UI | http://localhost:9011 |
| ClickHouse HTTP | http://localhost:8123 |
| Qdrant | http://localhost:6333/dashboard |

All ports are bound to 127.0.0.1 only.

## Decisions so far

- **SeaweedFS instead of MinIO**: MinIO stopped publishing Docker images in 2025. The pipeline only talks
  to the S3 API through boto3, so the storage backend is swappable.
- **Named volumes for all data**: the repo may live in a synced folder (OneDrive); database files must not.
- **Memory limits on every container**: the stack fits in ~8 GB so it runs on a 16 GB laptop next to Ollama.
