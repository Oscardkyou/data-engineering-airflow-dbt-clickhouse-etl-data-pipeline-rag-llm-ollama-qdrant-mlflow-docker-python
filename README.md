# Job Market Insights

Daily pipeline that collects IT job postings (hh.ru, Himalayas), lands them in an S3 data lake,
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

## Data sources

| Source | Type | Backfill | Status |
|---|---|---|---|
| [hh.ru API](https://api.hh.ru) | incremental (`date_from`/`date_to`, Kazakhstan) | yes | waiting for app token (`HH_ENABLED=false`) |
| [Himalayas](https://himalayas.app) remote jobs API | snapshot (open jobs only) | no, skipped | active |

Raw responses are stored untouched in `s3://raw/{source}/dt=YYYY-MM-DD/`. Each run replaces its
partition, so reruns and retries are idempotent.

Job data from [Himalayas](https://himalayas.app) is used under its API terms: listings link back
to Himalayas via `applicationLink` and are not redistributed to other job boards.

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
- **Assets instead of sensors**: `ingest` emits an asset event per source with `{source, dt}` in its extra;
  `load` is scheduled on those assets and maps one task per changed partition. No worker slot waits in a sensor.
- **Quality gate before the warehouse** (`jmi.quality`): Pydantic validation, dedupe, >10% invalid rows or
  <50% of the 7-day median volume fails the load. Every outcome is recorded in `raw.load_audit`.
  On real data it caught an ID collision: Himalayas job slugs repeat across companies, so the ID is `company/slug`.
- **Plain MergeTree partitioned by `(source, dt)`, not ReplacingMergeTree**: a reload is `DROP PARTITION` + `INSERT`,
  which is exact and immediate. ReplacingMergeTree only dedupes on background merges (or with `FINAL`).
  Cross-day versions of the same job are resolved in dbt.
- **Skills from a curated dictionary** (`jmi.skills`): deterministic and unit-tested; merged with hh `key_skills`.

- **dbt in its own virtualenv** inside the Airflow image: dbt pins libraries that conflict with Airflow's.
  `dbt build` runs models and tests in DAG order, so a failing test stops everything downstream of it.
- **Two currency providers**: Frankfurter (ECB, historical, no KZT) + hh.ru dictionaries (has KZT, today only).
  Cross rates go through USD; `ASOF JOIN` picks the latest rate on or before the day a vacancy was seen.
- **ClickHouse gotcha caught by tests**: a SELECT alias is visible in the whole query, so
  `ifNull(country, 'Worldwide') AS country` silently changed a hash key; the `relationships` test failed on all rows.
  Dimension models qualify source columns with a table alias.
- **Two chunking strategies indexed side by side** (`jmi.rag.chunking`): fixed word windows with overlap vs
  the posting's own sections (headings from `<h*>` or bold-only lines, EN/RU keywords classify them as
  requirements / responsibilities / benefits). Sections let a question about requirements filter to requirement
  chunks; stage 7 measures which retrieves better.
- **Contextual chunk header**: every embedded chunk starts with "title at company (seniority, location)" and its
  section, so "5+ years of Python" is not embedded without knowing which job it belongs to.
- **Incremental index by content hash** (`jmi.rag.index`): `doc_hash` (embedded text) and `meta_hash`
  (filterable fields) live in the Qdrant payload. Changed text is re-embedded, changed metadata is a payload
  update, vacancies gone from the marts are deleted. A rerun on unchanged data embeds nothing (0.1 s).
- **Reposts collapsed at query time**: some companies post one job under several URLs (15 groups, 46 rows on the
  first load); search returns one hit per distinct posting (`doc_hash`), not per vacancy id.

## Pipeline so far

```
ingest (daily) ──▶ s3://raw/{source}/dt=…/*.json ──asset──▶ load ──▶ quality gate
   └─ currency rates ──▶ raw.currency_rates                     ├──▶ s3://processed/{source}/dt=…/vacancies.parquet
                                                                └──▶ ClickHouse raw.vacancies + raw.load_audit
                                                                                │ asset
                                                                                ▼
                                          dbt_transform: source freshness ──▶ dbt build
                                                                                │ asset
                                                                                ▼
                       rag_index: marts ──▶ chunk (window | sections) ──▶ bge-m3 (Ollama) ──▶ Qdrant
```

## Vector index (Qdrant)

| Collection | Chunking | Points (399 vacancies) |
|---|---|---|
| `vacancies_window` | 350 words, 50 overlap | 931 |
| `vacancies_sections` | by heading, small sections merged, long ones windowed | 2015 |

Payload: vacancy metadata (title, company, url, seniority, remote, salary, skills, dates), `section`,
`section_kind`, chunk text and the two hashes. Indexed payload fields allow filtered search
(`jmi.rag.search.search(..., seniority="senior", section_kind="requirements", min_salary_usd=8000)`).
Sizes are in words: ~350 English words is ~470 bge-m3 tokens, far below its 8k limit, so the size is chosen for
retrieval precision (one topic per chunk), not to avoid truncation.

## Data model (dbt, ClickHouse `analytics`)

```
staging        stg_hh__vacancies, stg_himalayas__vacancies, stg_currency_rates      (views)
intermediate   int_vacancies_unified (latest version + first/last seen), int_currency_rates_daily,
               int_vacancy_salaries (monthly USD/KZT via ASOF JOIN)
marts          fct_vacancy ── dim_company, dim_location, dim_date
                    └── bridge_vacancy_skill ── dim_skill            dim_currency_rate
               mart_skill_demand (share + median salary by seniority), mart_daily_vacancies
```

Tests: keys unique/not null, fact→dimension relationships, accepted seniority values, composite
uniqueness, plausible monthly salary range, and a warning when a salary currency has no rate.

**SCD Type 2** is not used: vacancies are short-lived and we keep the latest version. It would matter
for attributes whose history affects analysis, e.g. a company changing industry or headquarters,
or a vacancy whose salary range is edited while open (to analyse "salary at publication time").
