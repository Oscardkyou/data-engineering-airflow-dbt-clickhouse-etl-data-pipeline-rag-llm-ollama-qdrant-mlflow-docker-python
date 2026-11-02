"""Dictionary-based skill extraction from free text.

Himalayas has no structured skills and hh's key_skills are often incomplete, so we also
scan title + description. A curated dictionary is deterministic, cheap and testable;
LLM-based extraction could come later and be compared against it.
"""

import html
import re

# canonical name -> regex alternatives (matched case-insensitively on word boundaries)
SKILLS: dict[str, list[str]] = {
    "Python": [r"python"],
    "SQL": [r"sql"],
    "Java": [r"java(?!script)"],
    "Scala": [r"scala"],
    "Go": [r"golang", r"go(?= developer| engineer)"],
    "JavaScript": [r"javascript", r"js"],
    "TypeScript": [r"typescript"],
    "Rust": [r"rust"],
    "C++": [r"c\+\+"],
    "Bash": [r"bash", r"shell scripting"],
    "Apache Airflow": [r"airflow"],
    "dbt": [r"dbt"],
    "Apache Spark": [r"spark", r"pyspark"],
    "Apache Kafka": [r"kafka"],
    "Apache Flink": [r"flink"],
    "Hadoop": [r"hadoop", r"hdfs", r"hive"],
    "ClickHouse": [r"clickhouse"],
    "PostgreSQL": [r"postgres(?:ql)?"],
    "MySQL": [r"mysql"],
    "MongoDB": [r"mongo(?:db)?"],
    "Redis": [r"redis"],
    "Elasticsearch": [r"elasticsearch", r"opensearch"],
    "Snowflake": [r"snowflake"],
    "BigQuery": [r"bigquery"],
    "Redshift": [r"redshift"],
    "Databricks": [r"databricks"],
    "Greenplum": [r"greenplum"],
    "Pandas": [r"pandas"],
    "NumPy": [r"numpy"],
    "PyTorch": [r"pytorch"],
    "TensorFlow": [r"tensorflow"],
    "scikit-learn": [r"scikit-learn", r"sklearn"],
    "LLM": [r"llms?", r"large language models?"],
    "RAG": [r"rag", r"retrieval[- ]augmented"],
    "LangChain": [r"langchain"],
    "MLflow": [r"mlflow"],
    "FastAPI": [r"fastapi"],
    "Django": [r"django"],
    "Flask": [r"flask"],
    "Docker": [r"docker"],
    "Kubernetes": [r"kubernetes", r"k8s"],
    "Terraform": [r"terraform"],
    "Ansible": [r"ansible"],
    "AWS": [r"aws", r"amazon web services"],
    "GCP": [r"gcp", r"google cloud"],
    "Azure": [r"azure"],
    "Linux": [r"linux"],
    "Git": [r"git(?!hub|lab)"],
    "CI/CD": [r"ci/cd", r"ci ?cd", r"github actions", r"gitlab ci", r"jenkins"],
    "Prometheus": [r"prometheus"],
    "Grafana": [r"grafana"],
    "Tableau": [r"tableau"],
    "Power BI": [r"power ?bi"],
    "ETL": [r"etl", r"elt"],
}

_PATTERNS = {
    # A trailing hyphen is allowed on purpose: Russian texts say "Python-разработчик", "ETL-процессы".
    name: re.compile(r"(?<![\w+#/.-])(?:" + "|".join(alts) + r")(?![\w+#])", re.IGNORECASE)
    for name, alts in SKILLS.items()
}
_TAGS = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    return html.unescape(_TAGS.sub(" ", raw or ""))


def extract_skills(*texts: str) -> list[str]:
    text = " ".join(texts)
    return sorted(name for name, pattern in _PATTERNS.items() if pattern.search(text))


def canonical_skill(name: str) -> str:
    """Map a free-form skill (e.g. hh key_skills 'Apache Airflow', 'Postgres') to the dictionary."""
    found = extract_skills(name)
    return found[0] if len(found) == 1 else name.strip()
