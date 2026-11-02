FROM apache/airflow:3.1.0-python3.12

# Install project deps pinned against Airflow itself so pip cannot upgrade/downgrade it.
COPY infra/airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /tmp/requirements.txt

# dbt lives in its own virtualenv: its pinned deps (protobuf, jinja, ...) would fight Airflow's.
COPY infra/airflow/requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python -m venv /home/airflow/dbt-venv \
    && /home/airflow/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt
