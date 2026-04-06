import sqlite3
import paramiko
import os
from urllib.parse import urlsplit
import datetime
import pandas as pd
import re
import time
import random
from paramiko.ssh_exception import SSHException
import posixpath
from dotenv import dotenv_values

env_vars = dotenv_values('.env')
TOKEN = env_vars['TOKEN']
DATABASE = env_vars['DATABASE']

def get_list_premium():
    conn = sqlite3.connect(DATABASE)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT nome FROM emby WHERE LOWER(nome) LIKE 'e%' ORDER BY nome"
        )
        rows = cur.fetchall()
        return [row[0] for row in rows if row and row[0]]
    finally:
        conn.close()

def get_server_ip_and_api_key(server):
    conn=sqlite3.connect(DATABASE)
    cursor=conn.cursor()
    cursor.execute("SELECT url, api FROM emby WHERE nome=?", (server,))
    result=cursor.fetchone()
    conn.close()
    if result:
        return result
    else:
        return None, None

def _parse_host(url_or_host: str) -> str:
    return (urlsplit(url_or_host if '://' in url_or_host else f'//{url_or_host}').hostname or url_or_host).strip('[]')

def _parse_and_insert(local_db_path: str):
    """Replica minimale della tua logica di parsing + insert in demo.db."""
    # Finestra temporale: ultimi 15 giorni
    current_time = datetime.datetime.now()
    two_months_ago = current_time - datetime.timedelta(days=60)
    two_months_ago_timestamp = int(two_months_ago.timestamp() * 1000)  # ms

    # Connessione al DB scaricato
    conn = sqlite3.connect(local_db_path)
    query = f"""
    SELECT Name 
    FROM ActivityLog
    WHERE Name LIKE '% ha avviato la riproduzione di %'
      AND DateCreatedMs >= {two_months_ago_timestamp}
    """
    data = pd.read_sql_query(query, conn)
    conn.close()

    # Funzione per estrarre username e device
    def parse_username_device(text):
        m = re.search(r"^(.*?) ha avviato.* su (.*)$", text or "")
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return None, None

    parsed_rows = []
    for _, row in data.iterrows():
        username, device = parse_username_device(row.get('Name'))
        if username and device:
            parsed_rows.append({'user': username, 'device': device})

    parsed_df = pd.DataFrame(parsed_rows)

    # (Opzionale) filtri device indesiderati
    # parsed_df = parsed_df[parsed_df['device'] != "Chrome Windows"]
    # parsed_df = parsed_df[parsed_df['device'] != "Chrome Android"]
    # parsed_df = parsed_df[parsed_df['device'] != "Chrome macOS"]

    # Righe univoche
    parsed_df = parsed_df.drop_duplicates()

    print("Anteprima parsed_df:")
    print(parsed_df.head())

    # Inserimento nel database demo.db (append)
    conn_demo = sqlite3.connect(DATABASE)
    parsed_df.to_sql('devices', conn_demo, if_exists='append', index=False)
    conn_demo.commit()
    conn_demo.close()

    print(f"✅ Inseriti {len(parsed_df)} record nella tabella 'devices' di demo.db.")

def calcoladevice_single(server, sftp, host, percorso):
    """
    Versione minimale della tua calcoladevice limitata allo scarico via SFTP (riusando la sessione già aperta)
    e al parsing+insert.
    """
    print(f"Calcolo dispositivi per il server: {server}")
    print(f"Connessione SSH già attiva con {host}. Scaricamento del file activitylog.db...")

    remote_path = posixpath.join(percorso, 'config', 'data', 'activitylog.db')  # ✅ sempre con '/'
    local_path = os.path.join(os.getcwd(), f'activitylog_{server}.db')

    sftp.get(remote_path, local_path)
    print(f"File scaricato da {remote_path} a {local_path}")

    # Parsing + insert (identico alla tua logica)
    _parse_and_insert(local_path)

    # Pulizia file temporaneo
    try:
        os.remove(local_path)
        print(f"File temporaneo eliminato: {local_path}")
    except Exception as e:
        print(f"Avviso: impossibile eliminare {local_path}: {e}")

def process_group_for_host(host, user, password, rows_for_host):
    """
    Apre UNA sola SSH/SFTP per l'host e processa tutti i server che puntano allo stesso IP/host.
    rows_for_host: lista di dict con chiavi: server, percorso
    """
    # piccolo retry/backoff per robustezza
    backoff = 1.0
    for attempt in range(3):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            print(f"\n=== Host {host} → servers: {[r['server'] for r in rows_for_host]} ===")
            ssh.connect(
                host, username=user, password=password, timeout=10,
                banner_timeout=10, auth_timeout=10, look_for_keys=False, allow_agent=False
            )
            # keepalive per evitare drop durante molte operazioni
            if ssh.get_transport() is not None:
                ssh.get_transport().set_keepalive(10)

            sftp = ssh.open_sftp()

            for r in rows_for_host:
                # Throttle leggero tra server sullo stesso host
                time.sleep(0.2)
                try:
                    calcoladevice_single(r['server'], sftp, host, r['percorso'])
                except Exception as e:
                    print(f"❌ Errore durante il processing di {r['server']} su {host}: {e}")

            try:
                sftp.close()
            except Exception:
                pass
            try:
                ssh.close()
            except Exception:
                pass
            return  # fatto

        except (TimeoutError, OSError, SSHException, Exception) as e:
            try:
                ssh.close()
            except Exception:
                pass
            if attempt == 2:
                print(f"❌ Host {host}: errore persistente: {e}")
                return
            sleep_s = backoff + random.uniform(0, 0.5)
            print(f"⚠️  {host}: errore '{e}'. Retry tra {sleep_s:.1f}s…")
            time.sleep(sleep_s)
            backoff *= 2

def svuotadevice():
    try:
        conn_demo = sqlite3.connect(DATABASE)
        cursor_demo = conn_demo.cursor()
        cursor_demo.execute("DELETE FROM devices")
        conn_demo.commit()
        conn_demo.close()
    except Exception as e:
        print(f"Errore durante lo svuotamento della tabella 'devices': {e}")

def calcoladevices():
    # carico la lista server
    server_names = get_list_premium()

    # 1) leggo una sola volta from DB emby e preparo raggruppamento per host, mantenendo minime modifiche
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    # mappa: (host, user, password) -> lista di {server, percorso}
    groups = {}
    for name in server_names:
        row = cur.execute("SELECT url, api, user, password, percorso FROM emby WHERE nome=?", (name,)).fetchone()
        if not row:
            print(f"❌ {name}: nessuna riga in emby")
            continue
        url, api_key, user, password, percorso = row
        host = _parse_host(url)
        groups.setdefault((host, user, password), []).append({
            'server': name,
            'percorso': percorso
        })
    conn.close()

    # 2) svuoto devices una volta sola prima di processare
    svuotadevice()

    # 3) per ogni host apro UNA sola SSH/SFTP e processo tutti i server su quell'host
    for (host, user, password), rows_for_host in groups.items():
        process_group_for_host(host, user, password, rows_for_host)

    print("\n✅ Completato.")


if __name__ == "__main__":
    # carico la lista server
    server_names = get_list_premium()

    # 1) leggo una sola volta from DB emby e preparo raggruppamento per host, mantenendo minime modifiche
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    # mappa: (host, user, password) -> lista di {server, percorso}
    groups = {}
    for name in server_names:
        row = cur.execute("SELECT url, api, user, password, percorso FROM emby WHERE nome=?", (name,)).fetchone()
        if not row:
            print(f"❌ {name}: nessuna riga in emby")
            continue
        url, api_key, user, password, percorso = row
        host = _parse_host(url)
        groups.setdefault((host, user, password), []).append({
            'server': name,
            'percorso': percorso
        })
    conn.close()

    # 2) svuoto devices una volta sola prima di processare
    svuotadevice()

    # 3) per ogni host apro UNA sola SSH/SFTP e processo tutti i server su quell'host
    for (host, user, password), rows_for_host in groups.items():
        process_group_for_host(host, user, password, rows_for_host)

    print("\n✅ Completato.")
