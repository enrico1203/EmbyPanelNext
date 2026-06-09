from __future__ import annotations

import datetime
import os
import posixpath
import random
import re
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit

import paramiko
from paramiko.ssh_exception import SSHException

from common import run_execute, run_many, run_select, send_telegram_message

DEFAULT_SSH_PORT = 22


def _parse_host(url_or_host: str) -> str:
    parsed = urlsplit(url_or_host if "://" in url_or_host else f"//{url_or_host}")
    return (parsed.hostname or url_or_host).strip("[]")


def _parse_override_map(env_name: str) -> dict[str, str]:
    """Legge una mappa `chiave:valore,chiave:valore` da una env var.

    Usata per gli override SSH, dato che l'url Emby (spesso dietro Cloudflare)
    non coincide con l'host/porta SSH reali:
        SSH_HOSTS=s2:78.47.86.60   -> host SSH reale (bypassa il proxy)
        SSH_PORTS=s2:7913          -> porta SSH non standard
    La chiave viene confrontata (case-insensitive) con il nome del server
    o con l'host estratto dall'url.
    """
    raw = os.getenv(env_name, "")
    result: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        key, _, value = item.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            result[key] = value
    return result


def _match_override(overrides: dict[str, str], nome: str, host: str) -> str | None:
    if not overrides:
        return None
    # candidati: nome server, host completo (es. "s2.dominio") e prima label host (es. "s2")
    for candidate in (nome, host, host.split(".")[0] if host else ""):
        key = candidate.strip().lower() if candidate else ""
        if key and key in overrides:
            return overrides[key]
    return None


def _resolve_ssh_host(overrides: dict[str, str], nome: str, url_host: str) -> str:
    return _match_override(overrides, nome, url_host) or url_host


def _resolve_ssh_port(overrides: dict[str, str], nome: str, url_host: str) -> int:
    raw = _match_override(overrides, nome, url_host)
    if raw is None:
        return DEFAULT_SSH_PORT
    try:
        return int(raw)
    except ValueError:
        print(f"[WARN] SSH_PORTS: porta non valida per '{nome or url_host}': {raw!r}")
        return DEFAULT_SSH_PORT


def get_list_premium() -> list[dict]:
    return run_select(
        """
        SELECT nome, url, "user", password, percorso
        FROM public.emby
        WHERE url IS NOT NULL AND url != ''
        ORDER BY nome
        """
    )


def parse_activitylog(local_db_path: str) -> list[dict]:
    current_time = datetime.datetime.now()
    since = current_time - datetime.timedelta(days=60)
    since_ms = int(since.timestamp() * 1000)

    conn = sqlite3.connect(local_db_path)
    try:
        rows = conn.execute(
            """
            SELECT Name
            FROM ActivityLog
            WHERE Name LIKE '% ha avviato la riproduzione di %'
              AND DateCreatedMs >= ?
            """,
            (since_ms,),
        ).fetchall()
    finally:
        conn.close()

    parsed: set[tuple[str, str]] = set()
    pattern = re.compile(r"^(.*?) ha avviato.* su (.*)$")
    for (name,) in rows:
        match = pattern.search(name or "")
        if not match:
            continue
        username = match.group(1).strip()
        device = match.group(2).strip()
        if username and device:
            parsed.add((username, device))

    return [{"user": username, "device": device} for username, device in sorted(parsed)]


def process_server_group(host: str, port: int, ssh_user: str, ssh_password: str, servers: list[dict]) -> list[dict]:
    backoff = 1.0
    last_error: Exception | None = None

    for attempt in range(3):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            print(f"=== Host {host}:{port} -> servers: {[server['nome'] for server in servers]} ===")
            ssh.connect(
                host,
                port=port,
                username=ssh_user,
                password=ssh_password,
                timeout=15,
                banner_timeout=15,
                auth_timeout=15,
                look_for_keys=False,
                allow_agent=False,
            )

            if ssh.get_transport() is not None:
                ssh.get_transport().set_keepalive(10)

            sftp = ssh.open_sftp()
            processed_servers: list[dict] = []

            try:
                for server in servers:
                    if not server["percorso"]:
                        print(f"[SKIP] {server['nome']}: percorso non configurato")
                        continue

                    remote_path = posixpath.join(server["percorso"], "config", "data", "activitylog.db")
                    tmpdir = tempfile.mkdtemp(prefix=f"devices2_{server['nome']}_")
                    local_path = os.path.join(tmpdir, "activitylog.db")

                    try:
                        sftp.get(remote_path, local_path)
                        # Il DB Emby gira in modalità WAL: tabelle e dati recenti stanno
                        # nei file -wal/-shm non ancora "checkpointati" nel .db principale.
                        # Vanno scaricati accanto al .db (stesso basename), altrimenti
                        # SQLite vede un database vuoto ("no such table: ActivityLog").
                        for ext in ("-wal", "-shm"):
                            try:
                                sftp.get(remote_path + ext, local_path + ext)
                            except IOError:
                                pass  # DB non in WAL o file assente: ok
                        print(f"[OK] {server['nome']}: scaricato {remote_path}")
                        server_rows = parse_activitylog(local_path)
                        processed_servers.append({
                            "server": server["nome"],
                            "rows": server_rows,
                        })
                    finally:
                        shutil.rmtree(tmpdir, ignore_errors=True)

                    time.sleep(0.2)
            finally:
                sftp.close()
                ssh.close()

            return processed_servers
        except (TimeoutError, OSError, SSHException, Exception) as exc:
            last_error = exc
            try:
                ssh.close()
            except Exception:
                pass

            if attempt == 2:
                break

            sleep_seconds = backoff + random.uniform(0, 0.5)
            print(f"[WARN] Host {host}:{port}: {exc}. Retry tra {sleep_seconds:.1f}s")
            time.sleep(sleep_seconds)
            backoff *= 2

    raise RuntimeError(f"Host {host}:{port}: errore persistente: {last_error}")


def run() -> None:
    servers = get_list_premium()
    if not servers:
        print("Nessun server Emby trovato.")
        return

    ssh_host_overrides = _parse_override_map("SSH_HOSTS")
    ssh_port_overrides = _parse_override_map("SSH_PORTS")

    groups: dict[tuple[str, int, str, str], list[dict]] = {}
    for server in servers:
        nome = server["nome"] or ""
        url_host = _parse_host(server["url"] or "")
        ssh_user = server["user"] or ""
        ssh_password = server["password"] or ""
        if not url_host or not ssh_user or not ssh_password:
            print(f"[SKIP] {nome}: host/user/password mancanti")
            continue
        ssh_host = _resolve_ssh_host(ssh_host_overrides, nome, url_host)
        port = _resolve_ssh_port(ssh_port_overrides, nome, url_host)
        groups.setdefault((ssh_host, port, ssh_user, ssh_password), []).append(server)

    send_telegram_message(f"Avvio devices2 su {len(groups)} host")

    all_rows: dict[tuple[str, str], dict] = {}
    errors: list[str] = []
    processed_count = 0

    run_execute('DELETE FROM public.devices')

    for (host, port, ssh_user, ssh_password), grouped_servers in groups.items():
        try:
            processed_servers = process_server_group(host, port, ssh_user, ssh_password, grouped_servers)
            for processed in processed_servers:
                processed_count += 1
                server_name = processed["server"]
                server_rows = processed["rows"]
                new_rows = []

                for row in server_rows:
                    key = (row["user"], row["device"])
                    if key in all_rows:
                        continue
                    all_rows[key] = row
                    new_rows.append(row)

                if new_rows:
                    run_many(
                        'INSERT INTO public.devices ("user", device) VALUES (:user, :device)',
                        new_rows,
                    )

                progress_message = (
                    f"devices2 [{processed_count}/{len(servers)}] {server_name}: "
                    f"{len(server_rows)} device letti, {len(new_rows)} nuovi inseriti, "
                    f"totale attuale {len(all_rows)}"
                )
                print(progress_message)
                send_telegram_message(progress_message)
        except Exception as exc:
            message = str(exc)
            errors.append(message)
            print(f"[ERRORE] {message}")
            send_telegram_message(f"devices2 errore host {host}: {message}")

    summary = (
        f"devices2 completato. Inseriti {len(all_rows)} record unici nella tabella devices."
    )
    if errors:
        summary += f" Errori: {len(errors)}"
    print(summary)
    if errors:
        print("\n".join(errors))

    send_telegram_message(summary if not errors else f"{summary}\n" + "\n".join(errors[:5]))


if __name__ == "__main__":
    run()
