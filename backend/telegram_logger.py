from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from decimal import Decimal

import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID") or os.getenv("IDCANALELOG", "")


def _fmt_amount(value: float | int | Decimal | None) -> str:
    if value is None:
        return "0"
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    text = format(amount, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def send_telegram_log(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL_ID:
        return

    chunks = [message[i:i + 3500] for i in range(0, len(message), 3500)] or [message]
    for chunk in chunks:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": str(TELEGRAM_CHANNEL_ID), "text": chunk},
                timeout=15,
            )
            response.raise_for_status()
        except Exception:
            return


def _fmt_date(value: datetime) -> str:
    return value.strftime("%d/%m/%Y")


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "utente"


def _send_telegram_document(chat_id: int | str, filename: str, content: str, caption: str) -> None:
    if not TELEGRAM_TOKEN or not chat_id:
        return

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": str(chat_id), "caption": caption},
            files={"document": (filename, content.encode("utf-8"), "text/calendar")},
            timeout=20,
        )
        response.raise_for_status()
    except Exception:
        return


def send_reseller_calendar_notification(
    *,
    chat_id: int | str | None,
    action: str,
    username: str,
    expiry_at: datetime,
    service: str | None = None,
    server_url: str | None = None,
) -> None:
    if not chat_id:
        return

    if action == "created":
        caption_lines = [
            f"Utente {username} creato.",
            f"Scadenza: {_fmt_date(expiry_at)}",
        ]
        if server_url:
            caption_lines.append(f"Server: {server_url}")
    else:
        caption_lines = [
            f"Utente {username} rinnovato.",
            f"Nuova scadenza: {_fmt_date(expiry_at)}",
        ]

    description_lines = [f"Scadenza: {_fmt_date(expiry_at)}"]
    if service:
        description_lines.append(f"Servizio: {service}")
    if server_url:
        description_lines.append(f"Server: {server_url}")

    start_date = expiry_at.strftime("%Y%m%d")
    end_date = (expiry_at + timedelta(days=1)).strftime("%Y%m%d")
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    summary = _ics_escape(f"Scadenza utente {username}")
    description = _ics_escape("\n".join(description_lines))
    uid = f"scadenza-{_safe_filename(username)}-{expiry_at.strftime('%Y%m%d')}@streaming-panel-next"
    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Streaming Panel Next//Reseller Calendar//IT\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART;VALUE=DATE:{start_date}\r\n"
        f"DTEND;VALUE=DATE:{end_date}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    _send_telegram_document(
        chat_id=chat_id,
        filename=f"scadenza-{_safe_filename(username)}.ics",
        content=ics_content,
        caption="\n".join(caption_lines),
    )


def log_user_created(
    *,
    actor: str,
    service: str,
    username: str,
    server: str,
    days: int,
    screens: int,
    cost: float | int | Decimal,
    remaining_credit: float | int | Decimal,
    extra: str | None = None,
) -> None:
    details = [
        "Nuova creazione utente",
        f"Reseller: {actor}",
        f"Servizio: {service}",
        f"Utente: {username}",
        f"Server: {server}",
        f"Giorni: {days}",
        f"Schermi: {screens}",
        f"Costo: {_fmt_amount(cost)} crediti",
        f"Credito residuo: {_fmt_amount(remaining_credit)}",
    ]
    if extra:
        details.append(extra)
    send_telegram_log("\n".join(details))


def log_user_renewed(
    *,
    actor: str,
    service: str,
    username: str,
    server: str,
    days: int,
    screens: int,
    cost: float | int | Decimal,
    remaining_credit: float | int | Decimal,
) -> None:
    send_telegram_log(
        "\n".join(
            [
                "Rinnovo utente",
                f"Reseller: {actor}",
                f"Servizio: {service}",
                f"Utente: {username}",
                f"Server: {server}",
                f"Giorni aggiunti: {days}",
                f"Schermi: {screens}",
                f"Costo: {_fmt_amount(cost)} crediti",
                f"Credito residuo: {_fmt_amount(remaining_credit)}",
            ]
        )
    )


def log_4k_change(
    *,
    actor: str,
    service: str,
    username: str,
    server: str,
    enabled: bool,
) -> None:
    send_telegram_log(
        "\n".join(
            [
                "Cambio stato 4K",
                f"Reseller: {actor}",
                f"Servizio: {service}",
                f"Utente: {username}",
                f"Server: {server}",
                f"Nuovo stato: {'attivato' if enabled else 'disattivato'}",
            ]
        )
    )


def log_user_deleted(
    *,
    actor: str,
    service: str,
    username: str,
    server: str,
) -> None:
    send_telegram_log(
        "\n".join(
            [
                "Cancellazione utente",
                f"Reseller: {actor}",
                f"Servizio: {service}",
                f"Utente: {username}",
                f"Server: {server}",
            ]
        )
    )


def log_reseller_recharge(
    *,
    actor: str,
    target: str,
    amount: float | int | Decimal,
    sender_remaining_credit: float | int | Decimal,
    target_new_credit: float | int | Decimal,
    target_role: str | None = None,
    created: bool = False,
) -> None:
    title = "Nuovo reseller creato" if created else "Ricarica reseller"
    lines = [
        title,
        f"Da: {actor}",
        f"A: {target}",
        f"Importo: {_fmt_amount(amount)} crediti",
        f"Credito mittente residuo: {_fmt_amount(sender_remaining_credit)}",
        f"Credito destinatario: {_fmt_amount(target_new_credit)}",
    ]
    if target_role:
        lines.append(f"Ruolo destinatario: {target_role}")
    send_telegram_log("\n".join(lines))
