from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI, Header, HTTPException, status

from scheduler_catalog import SCRIPTS_CATALOG
from scheduler_store import load_schedules, mutate_schedules

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INTERNAL_SECRET = os.getenv("SCHEDULER_SHARED_SECRET") or os.getenv("SECRET_KEY", "")

app = FastAPI(title="Streaming Panel Next Scheduler", version="1.0.0")
scheduler = BackgroundScheduler(daemon=True)
running_scripts: set[str] = set()
running_lock = threading.Lock()


def _require_internal_access(x_scheduler_secret: str | None = Header(default=None)) -> None:
    if not INTERNAL_SECRET or x_scheduler_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Accesso negato")


def _set_running(script_id: str, running: bool) -> None:
    def mutate(data: dict) -> None:
        data[script_id]["running"] = running

    mutate_schedules(mutate)


def _finalize_run(script_id: str, run_status: str, output: str) -> None:
    def mutate(data: dict) -> None:
        data[script_id]["running"] = False
        data[script_id]["last_run"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        data[script_id]["last_status"] = run_status
        data[script_id]["last_output"] = output

    mutate_schedules(mutate)


def _execute_script(script_id: str) -> None:
    script_meta = SCRIPTS_CATALOG[script_id]
    script_path = os.path.join(BASE_DIR, script_meta["script"])
    timeout_seconds = script_meta.get("timeout", 120)
    print(f"[Scheduler] Avvio {script_id}")

    _set_running(script_id, True)
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            cwd=BASE_DIR,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        combined_output = (result.stdout + result.stderr).strip()
        if not combined_output:
            combined_output = "Esecuzione completata senza output."
        combined_output = combined_output[:8000]
        run_status = "success" if result.returncode == 0 else "error"
        _finalize_run(script_id, run_status, combined_output)
        print(f"[Scheduler] {script_id} -> {run_status}")
    except subprocess.TimeoutExpired:
        timeout_message = f"Timeout dopo {timeout_seconds} secondi"
        _finalize_run(script_id, "error", timeout_message)
        print(f"[Scheduler] {script_id} -> error ({timeout_message})")
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        _finalize_run(script_id, "error", message)
        print(f"[Scheduler] {script_id} -> error ({message})")
    finally:
        with running_lock:
            running_scripts.discard(script_id)


def trigger_script(script_id: str) -> bool:
    if script_id not in SCRIPTS_CATALOG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script non trovato")

    with running_lock:
        if script_id in running_scripts:
            return False
        running_scripts.add(script_id)

    _set_running(script_id, True)
    thread = threading.Thread(target=_execute_script, args=(script_id,), daemon=True)
    thread.start()
    return True


def refresh_jobs() -> None:
    schedules = load_schedules()
    for script_id in SCRIPTS_CATALOG:
        job_id = f"sched_{script_id}"
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

        schedule_entry = schedules.get(script_id, {})
        hours = int(schedule_entry.get("interval_hours") or 0)
        enabled = bool(schedule_entry.get("enabled")) and hours > 0
        if enabled:
            scheduler.add_job(
                trigger_script,
                trigger=IntervalTrigger(hours=hours),
                id=job_id,
                args=[script_id],
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
            print(f"[Scheduler] Job '{script_id}' programmato ogni {hours} ore")


def reset_running_flags() -> None:
    def mutate(data: dict) -> None:
        for script_id in data:
            data[script_id]["running"] = False

    mutate_schedules(mutate)


@app.on_event("startup")
def on_startup() -> None:
    reset_running_flags()
    if not scheduler.running:
        scheduler.start()
    refresh_jobs()


@app.on_event("shutdown")
def on_shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/internal/reload")
def reload_scheduler(_: None = Depends(_require_internal_access)) -> dict:
    refresh_jobs()
    return {"status": "ok"}


@app.post("/internal/run/{script_id}")
def run_script(script_id: str, _: None = Depends(_require_internal_access)) -> dict:
    started = trigger_script(script_id)
    if not started:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Script gia in esecuzione")
    return {"status": "started", "script_id": script_id}
