from __future__ import annotations

import json
import os
from urllib import error, request

from fastapi import APIRouter, Depends, HTTPException, status

from auth import require_admin
from models import Reseller
from scheduler_catalog import SCRIPTS_CATALOG
from scheduler_store import load_schedules, mutate_schedules
from schemas import SchedulerResponse, SchedulerSaveRequest, SchedulerTaskResponse

router = APIRouter()

SCHEDULER_INTERNAL_URL = os.getenv("SCHEDULER_INTERNAL_URL", "http://nextscheduler:9092")
SCHEDULER_SHARED_SECRET = os.getenv("SCHEDULER_SHARED_SECRET") or os.getenv("SECRET_KEY", "")


def _build_response() -> SchedulerResponse:
    schedules = load_schedules()
    tasks = []
    for script_id, meta in SCRIPTS_CATALOG.items():
        saved = schedules.get(script_id, {})
        tasks.append(
            SchedulerTaskResponse(
                id=script_id,
                name=meta["name"],
                description=meta["description"],
                timeout=meta["timeout"],
                interval_hours=int(saved.get("interval_hours") or 0),
                enabled=bool(saved.get("enabled")),
                running=bool(saved.get("running")),
                last_run=saved.get("last_run"),
                last_status=saved.get("last_status"),
                last_output=saved.get("last_output"),
            )
        )
    return SchedulerResponse(tasks=tasks)


def _post_to_scheduler(path: str) -> None:
    url = f"{SCHEDULER_INTERNAL_URL}{path}"
    req = request.Request(
        url,
        method="POST",
        headers={"X-Scheduler-Secret": SCHEDULER_SHARED_SECRET},
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            if response.status >= 400:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Scheduler non raggiungibile")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        try:
            payload = json.loads(detail)
            detail = payload.get("detail", detail)
        except Exception:
            pass
        if exc.code == 409:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail or "Script gia in esecuzione")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail or "Errore dal servizio scheduler")
    except error.URLError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Servizio scheduler non raggiungibile")


@router.get("/scheduler", response_model=SchedulerResponse)
def get_scheduler_tasks(current_user: Reseller = Depends(require_admin)):
    return _build_response()


@router.put("/scheduler", response_model=SchedulerResponse)
def save_scheduler_tasks(
    payload: SchedulerSaveRequest,
    current_user: Reseller = Depends(require_admin),
):
    known_ids = set(SCRIPTS_CATALOG.keys())
    incoming_ids = {task.id for task in payload.tasks}
    invalid = incoming_ids - known_ids
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Script non validi: {', '.join(sorted(invalid))}",
        )

    def mutate(data: dict) -> None:
        for task in payload.tasks:
            data[task.id]["interval_hours"] = max(0, int(task.interval_hours))
            data[task.id]["enabled"] = bool(task.enabled) and int(task.interval_hours) > 0

    mutate_schedules(mutate)
    _post_to_scheduler("/internal/reload")
    return _build_response()


@router.post("/scheduler/{script_id}/run", response_model=SchedulerResponse)
def run_scheduler_task(
    script_id: str,
    current_user: Reseller = Depends(require_admin),
):
    if script_id not in SCRIPTS_CATALOG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script non trovato")
    _post_to_scheduler(f"/internal/run/{script_id}")
    return _build_response()
