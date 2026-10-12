"""Append-only audit trail for the agent loops: output/audit_trail.json.

The file is a JSON array. Each call appends one entry and rewrites the file
atomically; existing entries are never removed.
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from .llm import PROJECT_DIR
from .models import AuditEntry, TeamDeps

AUDIT_PATH = PROJECT_DIR / "output" / "audit_trail.json"
MAX_RESULT_CHARS = 400
MAX_DETAIL_CHARS = 1200

_lock = threading.Lock()


def short(value: Any, limit: int = MAX_RESULT_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _load() -> list[dict]:
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    with AUDIT_PATH.open(encoding="utf-8") as f:
        data = json.load(f)  # a corrupt file raises instead of being silently overwritten
    if not isinstance(data, list):
        raise ValueError(f"{AUDIT_PATH} must contain a JSON array.")
    return data


def _append(entry: AuditEntry) -> AuditEntry:
    with _lock:
        entries = _load()
        entries.append(entry.model_dump())
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)
    return entry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def read_entries() -> list[dict]:
    with _lock:
        return _load()


def record_human(actor: str, event: str, detail: str, *, ticket_id: int | None = None, **fields: Any) -> AuditEntry:
    """Append an entry for an action a person took through the API (approval, rejection, reset)."""
    return _append(AuditEntry(
        timestamp=_now(), run_id="human", ticket_id=ticket_id, agent=f"human:{actor}", depth=0, step=0,
        event=event, detail=short(detail, MAX_DETAIL_CHARS), **fields,
    ))


def record_desk(run_id: str, ticket_id: int, event: str, detail: str, **fields: Any) -> AuditEntry:
    """Append an entry for an automatic desk action (not an agent and not a person)."""
    return _append(AuditEntry(
        timestamp=_now(), run_id=run_id, ticket_id=ticket_id, agent="desk", depth=0, step=0,
        event=event, detail=short(detail, MAX_DETAIL_CHARS), **fields,
    ))


def record(deps: TeamDeps, event: str, detail: str, *, agent: str | None = None, **fields: Any) -> AuditEntry:
    """Append one entry for the current ticket run and return it."""
    return _append(AuditEntry(
        timestamp=_now(),
        run_id=deps.run_id,
        ticket_id=deps.ticket_id,
        agent=agent or deps.agent,
        depth=deps.depth,
        step=deps.counters.next_step(),
        event=event,
        detail=short(detail, MAX_DETAIL_CHARS),
        **fields,
    ))
