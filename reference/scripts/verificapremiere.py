#!/usr/bin/env python3
"""
Script: Verifica Premiere
Descrizione: Per ogni server Emby, effettua il login via Selenium e controlla
             lo stato Emby Premiere, aggiornando il campo 'limite' nel DB.
Esecuzione:  Lanciato dallo scheduler integrato di app.py (schedulazioni web).
"""
import os
import sys
import sqlite3
import time

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

try:
    from dotenv import dotenv_values
    env = dotenv_values(os.path.join(PROJECT_DIR, '.env'))
except ImportError:
    env = {}

DATABASE      = env.get('DATABASE')      or os.environ.get('DATABASE', '')
ROOT_PASSWORD = env.get('rootpassword')  or os.environ.get('rootpassword', '')
TOKEN         = env.get('TOKEN')         or os.environ.get('TOKEN', '')
ADMIN_ID      = env.get('admin')         or os.environ.get('admin', '')

MAX_RETRIES    = 3
RETRY_WAIT     = 60   # secondi di attesa tra un retry e l'altro
WAIT_BETWEEN   = 10   # secondi tra un server e l'altro


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(chat_id, text):
    if not TOKEN or not chat_id:
        print("  [SKIP] Telegram non configurato o chat_id mancante")
        return
    import requests
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": int(chat_id), "text": text},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"  [WARN] Telegram [{resp.status_code}]: {resp.json().get('description', resp.text)}")
    except Exception as e:
        print(f"  [WARN] Errore Telegram: {e}")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_servers(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT nome, url, tipo FROM emby WHERE url IS NOT NULL AND url != '' ORDER BY nome"
        ).fetchall()
    finally:
        conn.close()
    return rows


def update_limite(db_path, nome, valore):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute('UPDATE emby SET limite = ? WHERE nome = ?', (valore, nome))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Selenium
# ---------------------------------------------------------------------------

PREMIERE_RELOADS = 3   # ricaricamenti pagina premiere se testo non trovato
PREMIERE_WAIT    = 10  # secondi di attesa dopo ogni caricamento premiere


def _make_driver(base_url=''):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--incognito')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-application-cache')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    if base_url:
        options.add_argument(f'--unsafely-treat-insecure-origin-as-secure={base_url}')

    # In Docker è installato chromium, non chrome — specifica i path esplicitamente
    for binary in ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']:
        if os.path.exists(binary):
            options.binary_location = binary
            break

    for driver_path in ['/usr/bin/chromedriver', '/usr/lib/chromium/chromedriver']:
        if os.path.exists(driver_path):
            service = Service(executable_path=driver_path)
            break
    else:
        service = Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def _leggi_testo_premiere(driver, premiere_url):
    """
    Carica la pagina premiere, attende PREMIERE_WAIT secondi e legge il testo.
    Se il testo non è riconosciuto ricarica fino a PREMIERE_RELOADS volte.
    Ritorna 'no', 'quasi' o 'si', oppure None se dopo tutti i reload non trova nulla.
    """
    from selenium.webdriver.common.by import By

    for reload in range(PREMIERE_RELOADS):
        if reload == 0:
            driver.get(premiere_url)
        else:
            print(f"      Ricarico pagina premiere (tentativo {reload + 1}/{PREMIERE_RELOADS})...")
            driver.refresh()

        time.sleep(PREMIERE_WAIT)

        page_text = driver.find_element(By.TAG_NAME, 'body').text

        if "l'utilizzo del tuo dispositivo è nei limiti" in page_text:
            return "no"
        elif "ma l'utilizzo del tuo dispositivo è vicino al limite" in page_text:
            return "quasi"
        elif "ma sei oltre il limite del tuo dispositivo!" in page_text:
            return "si"
        else:
            print(f"      Testo non trovato. Estratto: {page_text[:200]!r}")

    return None


def _check_once(base_url, root_password):
    """
    Un singolo tentativo: login + navigazione a /embypremiere + lettura testo.
    Ritorna 'no', 'quasi' o 'si'. Solleva eccezione in caso di errore o testo non trovato.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    driver = _make_driver(base_url)
    try:
        # Apri il server (Emby redirige al login automaticamente)
        driver.get(base_url)

        wait = WebDriverWait(driver, 20)

        # Username
        username_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input.txtUserName'))
        )
        username_field.clear()
        username_field.send_keys('root')

        # Password
        password_field = driver.find_element(By.CSS_SELECTOR, 'input.txtPassword')
        password_field.clear()
        password_field.send_keys(root_password)

        # Submit
        driver.find_element(
            By.CSS_SELECTOR, 'button[type="submit"].paperSubmit'
        ).click()

        time.sleep(5)  # attendi completamento login

        # Vai alla pagina Premiere con attesa + reload se necessario
        premiere_url = f"{base_url}/web/index.html#!/embypremiere"
        result = _leggi_testo_premiere(driver, premiere_url)

        if result is None:
            raise ValueError("Testo Premiere non trovato dopo tutti i reload")

        return result

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def check_server(url, root_password, max_retries=MAX_RETRIES):
    """
    Tenta fino a max_retries volte. Ogni tentativo usa una sessione Chrome nuova.
    Ritorna (valore_limite, None) oppure (None, ultimo_errore) se tutti i tentativi falliscono.
    """
    import traceback
    base_url = url.rstrip('/')
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            result = _check_once(base_url, root_password)
            print(f"   [OK] Tentativo {attempt}: risultato = '{result}'")
            return result, None
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()
            print(f"   [ERRORE] Tentativo {attempt}/{max_retries}: {last_error}")
            print(tb)
            if attempt < max_retries:
                print(f"   Attendo {RETRY_WAIT}s prima di riprovare...")
                time.sleep(RETRY_WAIT)

    return None, last_error


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not DATABASE:
        print("ERRORE: DATABASE non configurato nel .env")
        sys.exit(1)

    db_path = DATABASE if os.path.isabs(DATABASE) else os.path.join(PROJECT_DIR, DATABASE)

    if not os.path.exists(db_path):
        print(f"ERRORE: Database non trovato: {db_path}")
        sys.exit(1)

    if not ROOT_PASSWORD:
        print("ERRORE: rootpassword non configurato nel .env")
        sys.exit(1)

    servers = get_servers(db_path)

    if not servers:
        print("Nessun server trovato nel database.")
        sys.exit(0)

    print(f"Server da verificare: {len(servers)}")

    send_telegram(ADMIN_ID, f"🔍 Avvio verifica Premiere su {len(servers)} server...")

    import traceback

    for i, (nome, url, tipo) in enumerate(servers):
        print(f"\n[{i+1}/{len(servers)}] Server: {nome} ({url}) [tipo: {tipo}]")

        try:
            result, last_error = check_server(url, ROOT_PASSWORD)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"   [ERRORE INATTESO] {last_error}")
            print(traceback.format_exc())
            send_telegram(ADMIN_ID, f"💥 [{i+1}/{len(servers)}] {nome}: errore inatteso — {last_error}")
            if i < len(servers) - 1:
                print(f"   Attesa {WAIT_BETWEEN}s prima del prossimo server...")
                time.sleep(WAIT_BETWEEN)
            continue

        if result is not None:
            update_limite(db_path, nome, result)
            print(f"   -> limite = '{result}' salvato nel DB")

            if result == "no":
                icona = "🟢"
            elif result == "quasi":
                icona = "🟡"
            elif result == "si":
                icona = "🔴"
            else:
                icona = "⚪"

            msg = f"{icona} [{i+1}/{len(servers)}] {nome}: {result}"
            if result == "si" and str(tipo).strip().lower() == "premium":
                msg += "\n⚠️ Server premium oltre il limite Premiere!"
            send_telegram(ADMIN_ID, msg)
        else:
            err_detail = f"\n❗ {last_error}" if last_error else ""
            print(f"   -> [SKIP] Impossibile verificare '{nome}', campo limite non aggiornato")
            send_telegram(ADMIN_ID, f"⚪ [{i+1}/{len(servers)}] {nome}: impossibile verificare{err_detail}")

        if i < len(servers) - 1:
            print(f"   Attesa {WAIT_BETWEEN}s prima del prossimo server...")
            time.sleep(WAIT_BETWEEN)

    print("\nCompletato.")

    # Riepilogo finale su Telegram
    try:
        lines = ["✅ Verifica Premiere completata\n"]
        for nome, url, tipo in servers:
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute("SELECT limite FROM emby WHERE nome = ?", (nome,)).fetchone()
                utenti = conn.execute("SELECT COUNT(*) FROM eUser WHERE server = ?", (nome,)).fetchone()[0]
            finally:
                conn.close()
            limite = row[0] if row else "?"
            if limite == "no":
                icona = "🟢"
            elif limite == "quasi":
                icona = "🟡"
            elif limite == "si":
                icona = "🔴"
            else:
                icona = "⚪"
            lines.append(f"{icona} {nome}: {limite} | 👥 {utenti} utenti")

        send_telegram(ADMIN_ID, "\n".join(lines))
    except Exception as e:
        print(f"[ERRORE] Riepilogo finale fallito: {e}")
        print(traceback.format_exc())
        send_telegram(ADMIN_ID, f"⚠️ Verifica completata ma riepilogo finale fallito: {e}")
