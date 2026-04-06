#!/usr/bin/env python3
"""
Script: Blocca Emby
Descrizione: Controlla le scadenze degli utenti Emby e disabilita automaticamente
             quelli scaduti, inserendoli nella tabella 'bloccati'.
Esecuzione:  Lanciato dallo scheduler integrato di app.py (schedulazioni web).
"""
import os
import sys
import sqlite3
import requests
from datetime import datetime, timedelta

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

try:
    from dotenv import dotenv_values
    env = dotenv_values(os.path.join(PROJECT_DIR, '.env'))
except ImportError:
    env = {}

TOKEN       = env.get('TOKEN')       or os.environ.get('TOKEN', '')
DATABASE    = env.get('DATABASE')    or os.environ.get('DATABASE', '')
IDCANALELOG = env.get('IDCANALELOG') or os.environ.get('IDCANALELOG', '')


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(chat_id, text):
    if not TOKEN or not chat_id:
        print("  [SKIP] Telegram non configurato o chat_id mancante")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": int(chat_id), "text": text}, timeout=10)
        if resp.status_code != 200:
            desc = resp.json().get('description', resp.text)
            print(f"  [WARN] Telegram [{resp.status_code}]: {desc}")
    except Exception as e:
        print(f"  [WARN] Errore Telegram: {e}")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def calc_expiry(date_str, expiry_days):
    if not date_str or expiry_days is None:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            base = datetime.strptime(str(date_str).strip(), fmt)
            return base + timedelta(days=int(expiry_days))
        except ValueError:
            continue
    return None


def get_expired_users(db_path):
    """Restituisce lista di (user, server) scaduti e non ancora in bloccati."""
    now = datetime.now()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            'SELECT user, date, expiry, server FROM eUser'
        ).fetchall()
        already_blocked = {
            r[0] for r in conn.execute('SELECT user FROM bloccati').fetchall()
        }
    finally:
        conn.close()

    expired = []
    for user, date_str, expiry_days, server in rows:
        if user in already_blocked:
            continue
        expiry_date = calc_expiry(date_str, expiry_days)
        if expiry_date and expiry_date < now:
            expired.append((user, server))
    return expired


def get_server_credentials(db_path, server_name):
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            'SELECT url, api FROM emby WHERE nome = ?', (server_name,)
        ).fetchone()
    finally:
        conn.close()
    if row:
        return str(row[0]), str(row[1])
    return None, None


def insert_bloccato(db_path, user, server):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            'INSERT OR IGNORE INTO bloccati (user, date, server) VALUES (?, ?, ?)',
            (user, date_str, server)
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Emby API
# ---------------------------------------------------------------------------

def get_user_id(server_url, api_key, username):
    headers = {'X-Emby-Token': api_key, 'Content-Type': 'application/json'}
    try:
        resp = requests.get(f"{server_url}/emby/Users", headers=headers, timeout=10)
        if resp.status_code == 200:
            users = resp.json()
            return next(
                (u['Id'] for u in users if u['Name'].lower() == username.lower()),
                None
            )
        print(f"  [WARN] get_user_id HTTP {resp.status_code} per '{username}'")
    except Exception as e:
        print(f"  [WARN] get_user_id errore: {e}")
    return None


def disable_user(server_url, api_key, user_id):
    headers = {'X-Emby-Token': api_key, 'Content-Type': 'application/json'}
    url = f"{server_url}/emby/Users/{user_id}/Policy"
    try:
        resp = requests.post(url, headers=headers, json={"IsDisabled": True}, timeout=10)
        return resp.status_code == 204
    except Exception as e:
        print(f"  [WARN] disable_user errore: {e}")
    return False


# ---------------------------------------------------------------------------
# Entry point (esecuzione singola — scheduling gestito da app.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not DATABASE:
        print("ERRORE: DATABASE non configurato nel .env")
        sys.exit(1)

    db_path = DATABASE if os.path.isabs(DATABASE) else os.path.join(PROJECT_DIR, DATABASE)

    if not os.path.exists(db_path):
        print(f"ERRORE: Database non trovato: {db_path}")
        sys.exit(1)

    print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] Avvio controllo scadenze Emby...")

    try:
        expired = get_expired_users(db_path)
    except Exception as e:
        print(f"ERRORE lettura DB: {e}")
        sys.exit(1)

    if not expired:
        print("Nessun utente scaduto da bloccare.")
        sys.exit(0)

    print(f"Utenti scaduti trovati: {len(expired)}")
    bloccati = 0
    errori   = 0

    for user, server in expired:
        print(f"-> Processo '{user}' (server: {server})")

        server_url, api_key = get_server_credentials(db_path, server)
        if not server_url:
            print(f"   [SKIP] Server '{server}' non trovato nel DB.")
            errori += 1
            continue

        user_id = get_user_id(server_url, api_key, user)
        if not user_id:
            print(f"   [SKIP] User ID non trovato su Emby per '{user}'.")
            errori += 1
            continue

        ok = disable_user(server_url, api_key, user_id)
        if ok:
            insert_bloccato(db_path, user, server)
            msg = f"L'utente {user} è stato bloccato sul server {server} in automatico"
            print(f"   [OK] {msg}")
            send_telegram(IDCANALELOG, msg)
            bloccati += 1
        else:
            print(f"   [ERRORE] Impossibile disabilitare '{user}' su Emby.")
            errori += 1

    print(f"Completato — Bloccati: {bloccati} | Errori: {errori}")
