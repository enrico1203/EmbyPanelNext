from __future__ import annotations

from common import TELEGRAM_CHANNEL_ID, send_telegram_message


def run() -> None:
    if not TELEGRAM_CHANNEL_ID:
        raise RuntimeError("TELEGRAM_CHANNEL_ID non configurato")
    send_telegram_message("FUNZIONA", TELEGRAM_CHANNEL_ID)
    print(f"OK: messaggio inviato al canale log {TELEGRAM_CHANNEL_ID}")


if __name__ == "__main__":
    run()
