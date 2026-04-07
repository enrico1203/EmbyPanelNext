from __future__ import annotations

SCRIPTS_CATALOG = {
    "telegram_test": {
        "name": "Test Telegram",
        "description": "Invia un messaggio di test al canale log Telegram configurato.",
        "script": "scripts/telegram_test.py",
        "timeout": 30,
    },
    "devices2": {
        "name": "Calcola Dispositivi",
        "description": "Scarica activitylog.db dai server Emby via SSH e aggiorna la tabella devices.",
        "script": "scripts/devices2.py",
        "timeout": 300,
    },
    "verificapremiere": {
        "name": "Verifica Premiere",
        "description": "Controlla lo stato Emby Premiere via Selenium e aggiorna il campo limite.",
        "script": "scripts/verificapremiere.py",
        "timeout": 1800,
    },
}


def default_schedule_entry() -> dict:
    return {
        "interval_hours": 0,
        "enabled": False,
        "last_run": None,
        "last_status": None,
        "last_output": None,
        "running": False,
    }
