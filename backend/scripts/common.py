from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(PROJECT_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("IDCANALELOG", "")
ROOT_PASSWORD = os.getenv("ROOT_PASSWORD") or os.getenv("rootpassword", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non configurato")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def run_select(sql: str, params: dict | None = None) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(text(sql), params or {})
        return [dict(row._mapping) for row in rows]


def run_execute(sql: str, params: dict | None = None) -> None:
    with engine.begin() as connection:
        connection.execute(text(sql), params or {})


def run_many(sql: str, params: Iterable[dict]) -> None:
    with engine.begin() as connection:
        connection.execute(text(sql), list(params))


def send_telegram_message(message: str, chat_id: str | None = None) -> None:
    chat_target = chat_id or TELEGRAM_CHANNEL_ID
    if not TELEGRAM_TOKEN or not chat_target:
        return

    chunks = [message[i:i + 3500] for i in range(0, len(message), 3500)] or [message]
    for chunk in chunks:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": str(chat_target), "text": chunk},
            timeout=15,
        )
        response.raise_for_status()
