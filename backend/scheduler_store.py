from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Callable

from scheduler_catalog import SCRIPTS_CATALOG, default_schedule_entry

SCHEDULES_FILE = os.getenv("SCHEDULES_FILE", "/app/schedules.json")


@contextmanager
def _locked_file(path: str):
    import fcntl

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        yield handle
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _normalize(data: dict | None) -> dict:
    normalized = data if isinstance(data, dict) else {}
    for script_id in SCRIPTS_CATALOG:
        entry = normalized.get(script_id)
        if not isinstance(entry, dict):
            entry = {}
        normalized[script_id] = {
            **default_schedule_entry(),
            **entry,
        }
    return normalized


def load_schedules() -> dict:
    with _locked_file(SCHEDULES_FILE) as handle:
        raw = handle.read().strip()
        if not raw:
            data = {}
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}

        normalized = _normalize(data)
        handle.seek(0)
        handle.truncate()
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        return normalized


def save_schedules(data: dict) -> dict:
    normalized = _normalize(data)
    with _locked_file(SCHEDULES_FILE) as handle:
        handle.seek(0)
        handle.truncate()
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return normalized


def mutate_schedules(mutator: Callable[[dict], None]) -> dict:
    data = load_schedules()
    mutator(data)
    return save_schedules(data)
