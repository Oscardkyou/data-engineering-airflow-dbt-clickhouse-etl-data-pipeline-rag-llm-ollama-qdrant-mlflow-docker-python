.PHONY: env up down ps logs smoke clean

env:  ## create .env with random local secrets
	python scripts/make_env.py

up:
	docker compose up -d --build

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=100

smoke:  ## run the infra smoke DAG inside Airflow
	docker compose exec airflow-scheduler airflow dags test infra_smoke

clean:  ## stop and DELETE all data volumes
	docker compose down -v
