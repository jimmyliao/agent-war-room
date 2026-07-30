"""Projection of internal steps to public-event.v1 JSONL and console timeline."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA = "agent-war-room.public-event.v1"
ALLOWED_TYPES = {
    "incident.started",
    "agent.delegated",
    "investigation.progress",
    "evidence.found",
    "review.accepted",
    "review.rejected",
    "approval.required",
    "incident.resolved",
    "incident.failed",
}
EMOJI = {
    "incident.started": "🚨",
    "agent.delegated": "📨",
    "investigation.progress": "🔎",
    "evidence.found": "🧾",
    "review.accepted": "✅",
    "review.rejected": "❌",
    "approval.required": "⏸️",
    "incident.resolved": "🏁",
    "incident.failed": "💥",
}


class PublicEventProjector:
    def __init__(
        self,
        incident_id: str,
        session_id: str,
        runs_root: Path,
    ) -> None:
        self.incident_id = incident_id
        self.session_id = session_id
        self.run_dir = runs_root / incident_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.run_dir / "events.jsonl"
        self.counts: Counter[str] = Counter()
        self.total = 0
        self.path.write_text("", encoding="utf-8")

    def emit(
        self,
        agent: str,
        event_type: str,
        summary: str,
        progress: int,
    ) -> dict[str, Any]:
        if event_type not in ALLOWED_TYPES:
            raise ValueError(f"unsupported public event type: {event_type}")

        clean_summary = " ".join(str(summary).split())
        if len(clean_summary) > 240:
            clean_summary = clean_summary[:237] + "..."

        event = {
            "schema": SCHEMA,
            "incidentId": self.incident_id,
            "sessionId": self.session_id,
            "eventId": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "type": event_type,
            "summary": clean_summary,
            "progress": max(0, min(100, int(progress))),
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")

        self.total += 1
        self.counts[event_type] += 1
        print(
            f"{EMOJI[event_type]} "
            f"[{event['progress']:>3}%] {agent} · {event_type} · {clean_summary}",
            flush=True,
        )
        return event

    def statistics(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_type": dict(sorted(self.counts.items())),
            "events_file": str(self.path),
        }
