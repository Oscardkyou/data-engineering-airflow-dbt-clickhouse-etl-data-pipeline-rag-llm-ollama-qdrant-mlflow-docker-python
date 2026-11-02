FROM python:3.12-slim

# The official MLflow image lacks the Postgres driver, so build a minimal one.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir mlflow==2.21.3 psycopg2-binary==2.9.10 boto3==1.37.38 sqlalchemy==2.0.40
