"""Commander orchestration for triage → investigate/critic critique loop."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from google.adk.agents import LoopAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agents import critic_agent, triage_agent
from .events import PublicEventProjector
from .investigator import build_round_prompt, investigator_agent

APP_NAME = "adk_debugging_war_room"
USER_ID = "war-room-operator"
# Bounded critique loop: the Critic may reject up to twice before a terminal
# decision. Override with MAX_ITERATIONS; a clean run resolves in ~2 rounds.
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "3"))

# ADK-native topology declaration mirrored by the commander's control loop.
critique_loop = LoopAgent(
    name="critique_loop",
    sub_agents=[investigator_agent, critic_agent],
    max_iterations=MAX_ITERATIONS,
)
war_room_pipeline = SequentialAgent(
    name="war_room_commander",
    sub_agents=[triage_agent, critique_loop],
)


@dataclass
class WarRoomResult:
    state: str
    triage_brief: dict[str, Any]
    investigation_report: str
    critic_verdict: dict[str, Any]
    iterations: int


def parse_json_object(value: Any) -> dict[str, Any]:
    """Parse JSON with tolerance for markdown fences and surrounding prose."""
    if isinstance(value, dict):
        return value
    if value is None:
        return {}

    text = str(value).strip()
    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)

    decoder = json.JSONDecoder()
    first_brace = text.find("{")
    if first_brace >= 0:
        candidates.append(text[first_brace:])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            try:
                parsed, _ = decoder.raw_decode(candidate.lstrip())
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
    return {}


def _event_text(event: Any) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(
        getattr(part, "text", "") or ""
        for part in parts
        if getattr(part, "text", None)
    ).strip()


async def _run_llm_agent(
    agent: Any,
    session_service: InMemorySessionService,
    session_id: str,
    message: str,
) -> str:
    runner = Runner(
        app_name=APP_NAME,
        agent=agent,
        session_service=session_service,
    )
    last_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=message)],
        ),
    ):
        text = _event_text(event)
        if text:
            last_text = text
    return last_text


async def _get_state(
    service: InMemorySessionService,
    session_id: str,
) -> dict[str, Any]:
    session = await service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )
    return dict(session.state) if session else {}


async def run_war_room(
    symptom: str,
    projector: PublicEventProjector,
) -> WarRoomResult:
    service = InMemorySessionService()
    session_id = projector.session_id
    await service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
        state={
            "incident_symptom": symptom,
            "triage_brief": "{}",
            "investigation_report": "",
            "critic_verdict": "{}",
        },
    )

    projector.emit(
        "commander",
        "incident.started",
        symptom,
        0,
    )
    projector.emit(
        "commander",
        "agent.delegated",
        "Delegated symptom classification to triage_agent.",
        10,
    )

    triage_text = await _run_llm_agent(
        triage_agent,
        service,
        session_id,
        symptom,
    )
    state = await _get_state(service, session_id)
    triage_raw = state.get("triage_brief") or triage_text
    triage = parse_json_object(triage_raw)
    if not triage:
        triage = {
            "suspected_domains": ["session state isolation"],
            "required_evidence": [
                "source evidence",
                "same-user two-thread controlled reproduction",
            ],
            "route": ["inspect service", "inspect session key", "reproduce"],
            "parse_warning": "triage output was not valid JSON",
        }

    projector.emit(
        "triage_agent",
        "investigation.progress",
        "Triage brief produced: "
        + ", ".join(map(str, triage.get("suspected_domains", []))),
        20,
    )

    missing: list[str] = []
    report = ""
    verdict: dict[str, Any] = {}
    final_state = "INCONCLUSIVE"

    for round_number in range(1, MAX_ITERATIONS + 1):
        progress = 25 + (round_number - 1) * 25
        projector.emit(
            "commander",
            "agent.delegated",
            f"Delegated investigation round {round_number} to investigator.",
            progress,
        )

        report = await _run_llm_agent(
            investigator_agent,
            service,
            session_id,
            build_round_prompt(triage, missing, round_number),
        )
        state = await _get_state(service, session_id)
        report = state.get("investigation_report") or report

        evidence_summary = (
            f"Investigation round {round_number} returned "
            f"{len(report)} characters of evidence."
        )
        projector.emit(
            "investigator",
            "evidence.found",
            evidence_summary,
            min(progress + 10, 82),
        )
        projector.emit(
            "commander",
            "agent.delegated",
            f"Delegated evidence review for round {round_number}.",
            min(progress + 14, 86),
        )

        critic_text = await _run_llm_agent(
            critic_agent,
            service,
            session_id,
            (
                f"Review investigation round {round_number}. "
                "Apply the controlled-reproduction acceptance rule strictly."
            ),
        )
        state = await _get_state(service, session_id)
        verdict_raw = state.get("critic_verdict") or critic_text
        verdict = parse_json_object(verdict_raw)
        if not verdict:
            verdict = {
                "accepted": False,
                "missing_evidence": ["critic output was not valid JSON"],
                "requested_action": "Return a valid evidence-based JSON verdict.",
            }

        accepted = verdict.get("accepted") is True
        missing_value = verdict.get("missing_evidence", [])
        missing = (
            [str(item) for item in missing_value]
            if isinstance(missing_value, list)
            else [str(missing_value)]
        )

        if accepted:
            projector.emit(
                "evidence_critic",
                "review.accepted",
                str(verdict.get("requested_action") or "Evidence accepted."),
                min(progress + 20, 94),
            )
            # Equivalent to escalating out of LoopAgent: acceptance terminates
            # the bounded critique loop and advances the incident to RESOLVED.
            final_state = "RESOLVED"
            break

        projector.emit(
            "evidence_critic",
            "review.rejected",
            str(
                verdict.get("requested_action")
                or "Evidence incomplete; reinvestigation required."
            ),
            min(progress + 20, 90),
        )

        if round_number < MAX_ITERATIONS:
            projector.emit(
                "commander",
                "investigation.progress",
                "State advanced to REINVESTIGATING: "
                + "; ".join(missing),
                min(progress + 22, 92),
            )

    if final_state == "RESOLVED":
        projector.emit(
            "commander",
            "incident.resolved",
            "Critic accepted the diagnosis and controlled reproduction evidence.",
            100,
        )
    else:
        projector.emit(
            "commander",
            "incident.failed",
            "Maximum critique iterations reached without accepted evidence.",
            100,
        )

    return WarRoomResult(
        state=final_state,
        triage_brief=triage,
        investigation_report=report,
        critic_verdict=verdict,
        iterations=round_number,
    )


def new_session_id() -> str:
    return str(uuid4())
