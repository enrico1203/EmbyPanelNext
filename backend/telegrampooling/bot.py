import html
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import psycopg2
import psycopg2.pool
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("telegrampooling")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "")
COOLDOWN_SECONDS = 5 * 60
MAX_QUERY_LEN = 100
ALLOWED_CHARS = re.compile(r"^[A-Za-z0-9._@+\-]+$")
POLL_TIMEOUT = 30

if not TELEGRAM_TOKEN:
    log.error("Missing TELEGRAM_TOKEN env var")
    sys.exit(1)
if not DATABASE_URL:
    log.error("Missing DATABASE_URL env var")
    sys.exit(1)

API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def _to_psycopg_dsn(url: str) -> str:
    # SQLAlchemy style "postgresql+psycopg2://..." -> plain "postgresql://..."
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://"):]
    if url.startswith("postgres+psycopg2://"):
        return "postgresql://" + url[len("postgres+psycopg2://"):]
    return url


DB_DSN = _to_psycopg_dsn(DATABASE_URL)

try:
    pool = psycopg2.pool.SimpleConnectionPool(1, 4, dsn=DB_DSN)
except Exception as exc:
    log.error("Unable to initialize DB pool: %s", exc)
    sys.exit(1)


cooldown: dict[int, float] = {}
_running = True


def _graceful_stop(*_):
    global _running
    _running = False
    log.info("Shutdown signal received")


signal.signal(signal.SIGTERM, _graceful_stop)
signal.signal(signal.SIGINT, _graceful_stop)


def _db_query(sql: str, params: tuple):
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    finally:
        pool.putconn(conn)


def _days_left(date, expiry) -> Optional[int]:
    if date is None or expiry is None:
        return None
    now = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return int(expiry) - (now - date).days


def _expiry_date(date, expiry) -> Optional[str]:
    if date is None or expiry is None:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return (date + timedelta(days=int(expiry))).strftime("%d/%m/%Y")


def _format_https(https: Optional[str]) -> Optional[str]:
    if not https:
        return None
    value = https.strip()
    if not value:
        return None
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.port:
        return value
    return f"{value}:443"


def lookup(query: str) -> Optional[dict]:
    # Emby: euser + emby (by server name)
    row = _db_query(
        """
        SELECT e.user, e.date, e.expiry, srv.https, srv.nome
        FROM public.euser e
        LEFT JOIN public.emby srv ON srv.nome = e.server
        WHERE LOWER(e.user) = LOWER(%s)
        LIMIT 1
        """,
        (query,),
    )
    if row:
        return {
            "service": "Emby",
            "user": row[0],
            "date": row[1],
            "expiry": row[2],
            "server_url": _format_https(row[3]),
            "server_name": row[4],
        }

    # Jellyfin: juser + jelly (by server name)
    row = _db_query(
        """
        SELECT j.user, j.date, j.expiry, srv.https, srv.nome
        FROM public.juser j
        LEFT JOIN public.jelly srv ON srv.nome = j.server
        WHERE LOWER(j.user) = LOWER(%s)
        LIMIT 1
        """,
        (query,),
    )
    if row:
        return {
            "service": "Jellyfin",
            "user": row[0],
            "date": row[1],
            "expiry": row[2],
            "server_url": _format_https(row[3]),
            "server_name": row[4],
        }

    # Plex: puser by email; the plex server is not exposed to end users,
    # they always log in via app.plex.tv
    row = _db_query(
        """
        SELECT pmail, date, expiry, server
        FROM public.puser
        WHERE LOWER(pmail) = LOWER(%s)
        LIMIT 1
        """,
        (query,),
    )
    if row:
        return {
            "service": "Plex",
            "user": row[0],
            "date": row[1],
            "expiry": row[2],
            "server_url": "https://app.plex.tv",
            "server_name": row[3],
        }

    return None


def format_response(info: dict) -> str:
    service = html.escape(info["service"])
    user = html.escape(str(info["user"] or "—"))
    expiry_date = _expiry_date(info["date"], info["expiry"]) or "—"
    days = _days_left(info["date"], info["expiry"])
    if days is None:
        status = ""
    elif days <= 0:
        status = f" (scaduto da {-days} giorni)"
    else:
        status = f" ({days} giorni rimanenti)"
    url = info.get("server_url")
    url_line = f"\nServer: <code>{html.escape(url)}</code>" if url else ""
    return (
        f"🎬 <b>Account {service} trovato</b>\n"
        f"Utente: <code>{user}</code>\n"
        f"Scadenza: <b>{html.escape(expiry_date)}</b>{html.escape(status)}"
        f"{url_line}"
    )


def send_message(chat_id: int, text: str) -> None:
    try:
        requests.post(
            f"{API_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        log.warning("sendMessage failed for %s: %s", chat_id, exc)


def handle_message(chat_id: int, text: str) -> None:
    now = time.monotonic()
    expires_at = cooldown.get(chat_id)
    if expires_at and expires_at > now:
        remaining = int(expires_at - now)
        send_message(
            chat_id,
            f"⏳ Hai già cercato un utente inesistente. Riprova tra {remaining // 60}m {remaining % 60}s.",
        )
        return

    query = (text or "").strip()
    if not query or len(query) > MAX_QUERY_LEN or not ALLOWED_CHARS.match(query):
        send_message(
            chat_id,
            "❌ Inserisci solo un username Emby/Jellyfin o un'email Plex (senza spazi o simboli strani).",
        )
        return

    try:
        info = lookup(query)
    except Exception as exc:
        log.exception("DB lookup failed: %s", exc)
        send_message(chat_id, "⚠️ Errore temporaneo, riprova più tardi.")
        return

    if info is None:
        cooldown[chat_id] = now + COOLDOWN_SECONDS
        send_message(
            chat_id,
            "L'username inserito non esiste, riprova fra 5 minuti.",
        )
        return

    send_message(chat_id, format_response(info))


def main() -> None:
    log.info("Telegram pooling bot avviato")
    offset: Optional[int] = None
    while _running:
        try:
            params = {"timeout": POLL_TIMEOUT, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset
            resp = requests.get(
                f"{API_URL}/getUpdates",
                params=params,
                timeout=POLL_TIMEOUT + 10,
            )
            if resp.status_code != 200:
                log.warning("getUpdates HTTP %s: %s", resp.status_code, resp.text[:200])
                time.sleep(5)
                continue
            data = resp.json()
            if not data.get("ok"):
                log.warning("getUpdates not ok: %s", data)
                time.sleep(5)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if not message:
                    continue
                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                text = message.get("text")
                if not chat_id or not isinstance(text, str):
                    continue
                if text.startswith("/"):
                    cmd = text.split()[0].split("@")[0].lower()
                    if cmd == "/start":
                        send_message(
                            chat_id,
                            "Benvenuto! Invia l'username del tuo account per ottenere i dati e la scadenza",
                        )
                    else:
                        send_message(
                            chat_id,
                            "Ciao! Scrivi qui il tuo username Emby/Jellyfin o la tua email Plex per controllare la scadenza.",
                        )
                    continue
                handle_message(chat_id, text)
        except requests.RequestException as exc:
            log.warning("Polling error: %s", exc)
            time.sleep(3)
        except Exception as exc:
            log.exception("Unexpected error: %s", exc)
            time.sleep(3)

    log.info("Bot stopped")


if __name__ == "__main__":
    main()
