#!/usr/bin/env python3
"""Run one ADK Debugging War Room incident."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# Vertex configuration must be present before importing/constructing ADK agents.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = "leapcore-dev"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

from warroom.commander import new_session_id, run_war_room
from warroom.events import PublicEventProjector

DEFAULT_SYMPTOM = "同一使用者在兩個 Discord threads 的對話內容互相污染"
ROOT = Path(__file__).resolve().parent


def make_incident_id(value: str | None) -> str:
    if value:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
        if cleaned:
            return cleaned
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"INC-SESSION-COLLISION-{timestamp}"


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the ADK Debugging War Room critique loop."
    )
    parser.add_argument(
        "symptom",
        nargs="?",
        default=DEFAULT_SYMPTOM,
        help="Incident symptom text.",
    )
    parser.add_argument(
        "--incident-id",
        help="Optional stable incident identifier.",
    )
    args = parser.parse_args()

    incident_id = make_incident_id(args.incident_id)
    session_id = new_session_id()
    projector = PublicEventProjector(
        incident_id=incident_id,
        session_id=session_id,
        runs_root=ROOT / "runs",
    )

    try:
        result = await run_war_room(args.symptom, projector)
    except Exception as error:
        projector.emit(
            "commander",
            "incident.failed",
            f"{type(error).__name__}: {error}",
            100,
        )
        print("\nFINAL RESULT")
        print(
            json.dumps(
                {
                    "incident_id": incident_id,
                    "state": "FAILED",
                    "error": f"{type(error).__name__}: {error}",
                    "event_statistics": projector.statistics(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    print("\nFINAL DIAGNOSIS")
    print(result.investigation_report)
    print("\nFINAL RESULT")
    print(
        json.dumps(
            {
                "incident_id": incident_id,
                "session_id": session_id,
                "state": result.state,
                "iterations": result.iterations,
                "triage_brief": result.triage_brief,
                "critic_verdict": result.critic_verdict,
                "event_statistics": projector.statistics(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.state == "RESOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
