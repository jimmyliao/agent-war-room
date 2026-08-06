#!/usr/bin/env python3
"""Cloud Trace spike: run the war room with OTel spans exported to Cloud Trace.

Set GOOGLE_CLOUD_PROJECT before running. incident-lab must be reachable at
INCIDENT_LAB_URL (default 127.0.0.1:8899, session_collision mode).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
logging.getLogger("google_adk.google.adk.runners").setLevel(logging.ERROR)

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
provider = TracerProvider(
    resource=Resource.create({"service.name": "agent-war-room"})
)
provider.add_span_processor(
    BatchSpanProcessor(CloudTraceSpanExporter(project_id=PROJECT))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("agent-war-room")

# Import AFTER the tracer provider is installed so ADK spans use it.
from warroom.commander import new_session_id, run_war_room  # noqa: E402
from warroom.events import PublicEventProjector  # noqa: E402

ROOT = Path(__file__).resolve().parent
SYMPTOM = "同一使用者在兩個 Discord threads 的對話內容互相污染"


async def main() -> int:
    incident_id = "INC-TRACE-" + datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    projector = PublicEventProjector(
        incident_id=incident_id,
        session_id=new_session_id(),
        runs_root=ROOT / "runs",
    )
    with tracer.start_as_current_span("war_room_incident") as span:
        span.set_attribute("incident.id", incident_id)
        span.set_attribute("incident.symptom", SYMPTOM)
        result = await run_war_room(SYMPTOM, projector)
        span.set_attribute("incident.state", result.state)
        span.set_attribute("incident.iterations", result.iterations)

    print("\nFINAL RESULT")
    print(
        json.dumps(
            {
                "incident_id": incident_id,
                "state": result.state,
                "iterations": result.iterations,
                "event_statistics": projector.statistics(),
                "trace_project": PROJECT,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.state == "RESOLVED" else 2


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    finally:
        provider.force_flush()
        provider.shutdown()
    print(
        f"\n>>> Spans flushed to Cloud Trace (project={PROJECT}). "
        "Console: Trace Explorer → service.name=agent-war-room"
    )
    raise SystemExit(code)
