import pytest

from jmi.skills import canonical_skill, extract_skills, html_to_text


@pytest.mark.parametrize(("text", "expected"), [
    ("Python, SQL and Airflow", {"Python", "SQL", "Apache Airflow"}),
    ("JavaScript developer", {"JavaScript"}),          # not "Java"
    ("Java 17, Spring", {"Java"}),
    ("PySpark on Databricks", {"Apache Spark", "Databricks"}),
    ("PostgreSQL / Postgres", {"PostgreSQL"}),
    ("GitHub Actions CI", {"CI/CD"}),                    # not "Git"
    ("we love C++ and K8s", {"C++", "Kubernetes"}),
    ("NoSQL experience", set()),                         # "sql" inside a word is not SQL
    ("ragged edges", set()),                             # "rag" inside a word is not RAG
    ("Python-разработчик, ETL-процессы", {"Python", "ETL"}),
])
def test_extract_skills(text, expected):
    assert set(extract_skills(text)) == expected


def test_html_is_stripped():
    assert "Airflow & dbt" in html_to_text("<li>Airflow &amp; dbt</li>")


def test_canonical_skill_maps_known_and_keeps_unknown():
    assert canonical_skill("Apache Airflow") == "Apache Airflow"
    assert canonical_skill("Postgres") == "PostgreSQL"
    assert canonical_skill(" Agile ") == "Agile"
