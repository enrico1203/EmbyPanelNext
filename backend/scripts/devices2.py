from __future__ import annotations

import datetime
import os
import posixpath
import random
import re
import sqlite3
import tempfile
import time
from urllib.parse import urlsplit

import paramiko
from paramiko.ssh_exception import SSHException

from common import run_execute, run_many, run_select, send_telegram_message


def _parse_host(url_or_host: str) -> str:
    parsed = urlsplit(url_or_host if "://" in url_or_host else f"//{url_or_host}")
    return (parsed.hostname or url_or_host).strip("[]")


def get_list_premium() -> list[dict]:
    return run_select(
        """
        SELECT nome, url, "user", password, percorso
        FROM public.emby
        WHERE LOWER(nome) LIKE 'e%'
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


def process_server_group(host: str, ssh_user: str, ssh_password: str, servers: list[dict]) -> list[dict]:
    backoff = 1.0
    last_error: Exception | None = None

    for attempt in range(3):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            print(f"=== Host {host} -> servers: {[server['nome'] for server in servers]} ===")
            ssh.connect(
                host,
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
                    with tempfile.NamedTemporaryFile(suffix=f"_{server['nome']}.db", delete=False) as tmp:
                        local_path = tmp.name

                    try:
                        sftp.get(remote_path, local_path)
                        print(f"[OK] {server['nome']}: scaricato {remote_path}")
                        server_rows = parse_activitylog(local_path)
                        processed_servers.append({
                            "server": server["nome"],
                            "rows": server_rows,
                        })
                    finally:
                        if os.path.exists(local_path):
                            os.remove(local_path)

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
            print(f"[WARN] Host {host}: {exc}. Retry tra {sleep_seconds:.1f}s")
            time.sleep(sleep_seconds)
            backoff *= 2

    raise RuntimeError(f"Host {host}: errore persistente: {last_error}")


def run() -> None:
    servers = get_list_premium()
    if not servers:
        print("Nessun server Emby trovato.")
        return

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for server in servers:
        host = _parse_host(server["url"] or "")
        ssh_user = server["user"] or ""
        ssh_password = server["password"] or ""
        if not host or not ssh_user or not ssh_password:
            print(f"[SKIP] {server['nome']}: host/user/password mancanti")
            continue
        groups.setdefault((host, ssh_user, ssh_password), []).append(server)

    send_telegram_message(f"Avvio devices2 su {len(groups)} host")

    all_rows: dict[tuple[str, str], dict] = {}
    errors: list[str] = []
    processed_count = 0

    run_execute('DELETE FROM public.devices')

    for (host, ssh_user, ssh_password), grouped_servers in groups.items():
        try:
            processed_servers = process_server_group(host, ssh_user, ssh_password, grouped_servers)
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
