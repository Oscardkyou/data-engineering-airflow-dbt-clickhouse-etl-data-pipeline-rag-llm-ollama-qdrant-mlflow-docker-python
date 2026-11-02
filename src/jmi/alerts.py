"""Failure alerts: always to the task log, to Telegram when a bot token is configured."""

import logging
import os

import httpx

log = logging.getLogger(__name__)


def notify(text: str) -> None:
    log.error("ALERT: %s", text)
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return
    try:
        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat_id, "text": text[:4000]}, timeout=10).raise_for_status()
    except httpx.HTTPError as exc:  # an alerting failure must never mask the original one
        log.warning("telegram alert failed: %s", exc)


def on_task_failure(context) -> None:
    """Airflow on_failure_callback."""
    ti = context["task_instance"]
    notify(f"❌ {ti.dag_id}.{ti.task_id} failed (run {context['run_id']}, try {ti.try_number}).\n"
           f"{context.get('exception')}")
