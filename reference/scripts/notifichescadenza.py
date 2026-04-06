#!/usr/bin/env python3
"""
Script: Notifiche Scadenza
Descrizione: Controlla le scadenze degli utenti Plex/Emby/Jellyfin e invia
             notifiche Telegram a chi scade entro 4 giorni.
"""
import os
import sys
import sqlite3
import requests
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PROJECT_DIR, '.env')

try:
    from dotenv import dotenv_values
    env = dotenv_values(ENV_PATH)
except ImportError:
    env = {}

TOKEN    = env.get('TOKEN')    or os.environ.get('TOKEN', '')
DATABASE = env.get('DATABASE') or os.environ.get('DATABASE', '')

DAYS_THRESHOLD = 4


def send_telegram(chat_id, text):
    if not TOKEN:
        print("  ERRORE: TOKEN non configurato")
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": int(chat_id), "text": text}, timeout=10)
        if resp.status_code == 200:
            print(f"  -> Notifica inviata a {chat_id}")
            return True
        else:
            desc = resp.json().get('description', resp.text)
            print(f"  -> ERRORE Telegram [{resp.status_code}]: {desc}")
            return False
    except Exception as e:
        print(f"  -> ERRORE richiesta: {e}")
        return False


def calc_expiry(date_str, expiry_days):
    """Restituisce la data di scadenza (datetime) oppure None se i dati sono mancanti/invalidi."""
    if not date_str or expiry_days is None:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            base = datetime.strptime(str(date_str).strip(), fmt)
            return base + timedelta(days=int(expiry_days))
        except ValueError:
            continue
    return None


def check_table(conn, table, platform):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Plex usa 'pmail' come identificativo, Emby/Jellyfin usano 'user'
    identity_col = "pmail" if table == "User" else "user"

    try:
        rows = conn.execute(f'SELECT id, date, expiry, "{identity_col}" FROM "{table}"').fetchall()
    except Exception as e:
        print(f"  ERRORE lettura tabella {table}: {e}")
        return

    notified = 0
    skipped  = 0

    for chat_id, date_str, expiry_days, identity in rows:
        if not chat_id:
            skipped += 1
            continue

        expiry_date = calc_expiry(date_str, expiry_days)
        if expiry_date is None:
            skipped += 1
            continue

        days_left = (expiry_date.replace(hour=0, minute=0, second=0, microsecond=0) - today).days

        if 1 <= days_left <= DAYS_THRESHOLD:
            giorni = "giorno" if days_left == 1 else "giorni"
            identity_label = "Email" if table == "User" else "Username"
            identity_line = f"{identity_label}: {identity}\n" if identity else ""
            msg = (
                f"Il tuo account {platform} scadrà fra {days_left} {giorni}.\n"
                f"{identity_line}"
                f"Se non viene rinnovato verrà cancellato."
            )
            send_telegram(chat_id, msg)
            notified += 1

    print(f"[{platform}] Totale: {len(rows)} | Notificati: {notified} | Saltati: {skipped}")


if __name__ == "__main__":
    if not DATABASE:
        print("ERRORE: DATABASE non configurato nel .env")
        sys.exit(1)

    # Supporta sia percorsi assoluti che relativi (relativi alla root del progetto)
    db_path = DATABASE if os.path.isabs(DATABASE) else os.path.join(PROJECT_DIR, DATABASE)

    if not os.path.exists(db_path):
        print(f"ERRORE: Database non trovato: {db_path}")
        sys.exit(1)

    print(f"Controllo scadenze — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Soglia notifica: entro {DAYS_THRESHOLD} giorni\n")

    conn = sqlite3.connect(db_path)
    try:
        check_table(conn, "User",  "Plex")
        check_table(conn, "eUser", "Emby")
        check_table(conn, "jUser", "Jellyfin")
    finally:
        conn.close()

    print("\nCompletato.")
