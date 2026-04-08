from __future__ import annotations

from datetime import datetime, timedelta, timezone

from common import run_select, send_telegram_message
import jellyapi


def _to_aware_datetime(value) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    raw = str(value).strip()
    if not raw:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _expiry_date(start_date, expiry_days) -> datetime | None:
    base = _to_aware_datetime(start_date)
    if base is None or expiry_days is None:
        return None

    try:
        days = int(expiry_days)
    except (TypeError, ValueError):
        return None

    return base + timedelta(days=days)


def _load_users() -> list[dict]:
    return run_select(
        """
        SELECT invito, "user", server, date, expiry, schermi
        FROM public.juser
        WHERE "user" IS NOT NULL
          AND TRIM("user") != ''
          AND server IS NOT NULL
          AND TRIM(server) != ''
        ORDER BY server, "user"
        """
    )


def _get_disabled_state(server_name: str, user_id: str) -> bool | None:
    try:
        policy = jellyapi.get_user_policy(server_name, user_id)
        if isinstance(policy, dict) and "IsDisabled" in policy:
            return bool(policy.get("IsDisabled"))
    except Exception:
        pass

    try:
        info = jellyapi.get_user_info(server_name, user_id)
        if isinstance(info, dict):
            policy = info.get("Policy")
            if isinstance(policy, dict) and "IsDisabled" in policy:
                return bool(policy.get("IsDisabled"))
            if "IsDisabled" in info:
                return bool(info.get("IsDisabled"))
    except Exception:
        pass

    return None


def run() -> None:
    now = datetime.now(timezone.utc)
    rows = _load_users()

    expired_rows = []
    for row in rows:
        expires_at = _expiry_date(row.get("date"), row.get("expiry"))
        if expires_at and expires_at < now:
            expired_rows.append({**row, "expires_at": expires_at})

    if not expired_rows:
        print("bloccautentijelly: nessun utente scaduto da bloccare.")
        return

    blocked_now = 0
    already_disabled = 0
    skipped = 0
    errors: list[str] = []

    print(f"bloccautentijelly: utenti scaduti trovati {len(expired_rows)}")

    for row in expired_rows:
        username = (row.get("user") or "").strip()
        server_name = (row.get("server") or "").strip()
        stream_limit = int(row.get("schermi") or 1)

        if not username or not server_name:
            skipped += 1
            continue

        try:
            user_id = jellyapi.get_user_id(server_name, username)
            if not user_id:
                raise RuntimeError(f"user id non trovato per {username} su {server_name}")

            disabled_state = _get_disabled_state(server_name, user_id)
            if disabled_state is True:
                already_disabled += 1
                print(f"bloccautentijelly: {username} su {server_name} gia bloccato")
                continue

            jellyapi.disable_user(server_name, user_id, stream_limit)
            blocked_now += 1

            message = f"bloccautentijelly: utente {username} bloccato sul server {server_name}"
            print(message)
            send_telegram_message(message)
        except Exception as exc:
            error_message = f"bloccautentijelly: errore su {username}@{server_name}: {type(exc).__name__}: {exc}"
            errors.append(error_message)
            print(error_message)
            send_telegram_message(error_message)

    summary = (
        f"bloccautentijelly completato. Scaduti: {len(expired_rows)} | "
        f"bloccati ora: {blocked_now} | gia bloccati: {already_disabled} | "
        f"saltati: {skipped} | errori: {len(errors)}"
    )
    print(summary)
    if blocked_now or errors:
        send_telegram_message(summary)


if __name__ == "__main__":
    run()
