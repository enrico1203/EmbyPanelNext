from __future__ import annotations

import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from common import ROOT_PASSWORD, run_execute, run_select, send_telegram_message

MAX_RETRIES = 3
RETRY_WAIT = 60
WAIT_BETWEEN = 10
PREMIERE_RELOADS = 3
PREMIERE_WAIT = 10


def get_servers() -> list[dict]:
    return run_select(
        """
        SELECT nome, url, tipo
        FROM public.emby
        WHERE url IS NOT NULL AND url != ''
        ORDER BY nome
        """
    )


def update_limite(nome: str, valore: str) -> None:
    run_execute(
        'UPDATE public.emby SET limite = :valore WHERE nome = :nome',
        {"nome": nome, "valore": valore},
    )


def _make_driver(base_url: str = ""):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--incognito")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-application-cache")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    if base_url:
        options.add_argument(f"--unsafely-treat-insecure-origin-as-secure={base_url}")

    for binary in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.path.exists(binary):
            options.binary_location = binary
            break

    for driver_path in ["/usr/bin/chromedriver", "/usr/lib/chromium/chromedriver"]:
        if os.path.exists(driver_path):
            service = Service(executable_path=driver_path)
            break
    else:
        service = Service()

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(30)
    return driver


def _read_premiere_status(driver, premiere_url: str) -> str | None:
    for reload_index in range(PREMIERE_RELOADS):
        if reload_index == 0:
            driver.get(premiere_url)
        else:
            print(f"Ricarico pagina premiere ({reload_index + 1}/{PREMIERE_RELOADS})...")
            driver.refresh()

        time.sleep(PREMIERE_WAIT)
        page_text = driver.find_element(By.TAG_NAME, "body").text

        if "l'utilizzo del tuo dispositivo è nei limiti" in page_text:
            return "no"
        if "ma l'utilizzo del tuo dispositivo è vicino al limite" in page_text:
            return "quasi"
        if "ma sei oltre il limite del tuo dispositivo!" in page_text:
            return "si"
        print(f"Testo non trovato. Estratto: {page_text[:200]!r}")

    return None


def _check_once(base_url: str, root_password: str) -> str:
    driver = _make_driver(base_url)
    try:
        driver.get(base_url)
        wait = WebDriverWait(driver, 20)

        username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.txtUserName")))
        username_field.clear()
        username_field.send_keys("root")

        password_field = driver.find_element(By.CSS_SELECTOR, "input.txtPassword")
        password_field.clear()
        password_field.send_keys(root_password)

        driver.find_element(By.CSS_SELECTOR, "button[type='submit'].paperSubmit").click()
        time.sleep(5)

        result = _read_premiere_status(driver, f"{base_url.rstrip('/')}/web/index.html#!/embypremiere")
        if result is None:
            raise RuntimeError("Testo Premiere non trovato dopo tutti i tentativi")
        return result
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def check_server(url: str, root_password: str) -> tuple[str | None, str | None]:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _check_once(url.rstrip("/"), root_password)
            print(f"[OK] Tentativo {attempt}: risultato = {result}")
            return result, None
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            print(f"[ERRORE] Tentativo {attempt}/{MAX_RETRIES}: {last_error}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
    return None, last_error


def run() -> None:
    if not ROOT_PASSWORD:
        raise RuntimeError("ROOT_PASSWORD/rootpassword non configurato")

    servers = get_servers()
    if not servers:
        print("Nessun server trovato nel database.")
        return

    send_telegram_message(f"Avvio verifica Premiere su {len(servers)} server.")

    summary_lines = []
    for index, server in enumerate(servers, start=1):
        nome = server["nome"]
        url = server["url"]
        tipo = server.get("tipo")
        print(f"[{index}/{len(servers)}] Server: {nome} ({url}) [tipo: {tipo}]")

        result, error = check_server(url, ROOT_PASSWORD)
        if result is not None:
            update_limite(nome, result)
            icon = "🟢" if result == "no" else "🟡" if result == "quasi" else "🔴"
            line = f"{icon} {nome}: {result}"
            summary_lines.append(line)
            send_telegram_message(line)
        else:
            line = f"⚪ {nome}: impossibile verificare"
            if error:
                line += f" ({error})"
            summary_lines.append(line)
            send_telegram_message(line)

        if index < len(servers):
            time.sleep(WAIT_BETWEEN)

    final_message = "Verifica Premiere completata.\n" + "\n".join(summary_lines)
    print(final_message)
    send_telegram_message(final_message)


if __name__ == "__main__":
    run()
