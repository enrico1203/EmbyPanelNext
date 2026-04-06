#!/usr/bin/env python3
"""
Script: Test Telegram
Descrizione: Invia il messaggio "FUNZIONA" al chat ID configurato via Telegram Bot API.
Configurazione richiesta: TOKEN nel file .env nella cartella radice del progetto.
"""
import os
import sys
import requests

# Percorso progetto (cartella padre rispetto a scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PROJECT_DIR, '.env')

# Carica .env
try:
    from dotenv import dotenv_values
    env = dotenv_values(ENV_PATH)
except ImportError:
    env = {}

TELEGRAM_TOKEN = env.get('TOKEN') or os.environ.get('TOKEN', '')
CHAT_ID = 6978931930


def run():
    if not TELEGRAM_TOKEN:
        print("ERRORE: TOKEN non trovato nel file .env")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "FUNZIONA"
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f"OK: Messaggio inviato a {CHAT_ID}")
        else:
            data = resp.json()
            print(f"ERRORE Telegram [{resp.status_code}]: {data.get('description', resp.text)}")
            sys.exit(1)
    except requests.exceptions.Timeout:
        print("ERRORE: Timeout connessione a Telegram")
        sys.exit(1)
    except Exception as e:
        print(f"ERRORE: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
