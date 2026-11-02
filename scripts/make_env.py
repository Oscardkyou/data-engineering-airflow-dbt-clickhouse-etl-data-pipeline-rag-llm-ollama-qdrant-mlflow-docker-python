"""Create .env from .env.example, filling passwords and keys with random values."""

import base64
import pathlib
import secrets

ROOT = pathlib.Path(__file__).resolve().parent.parent
GENERATED = {
    "POSTGRES_PASSWORD": lambda: secrets.token_urlsafe(16),
    "S3_SECRET_KEY": lambda: secrets.token_urlsafe(16),
    "CLICKHOUSE_PASSWORD": lambda: secrets.token_urlsafe(16),
    "AIRFLOW_FERNET_KEY": lambda: base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    "AIRFLOW_JWT_SECRET": lambda: secrets.token_urlsafe(32),
}


def main() -> None:
    target = ROOT / ".env"
    if target.exists():
        print(".env already exists, leaving it untouched")
        return
    lines = []
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={GENERATED[key]()}" if key in GENERATED else line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("created .env")


if __name__ == "__main__":
    main()
