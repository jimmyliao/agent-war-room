#!/usr/bin/env python3
"""M3: deploy the full war_room_pipeline (Triage -> Loop[Investigator, Critic])
to GEAP Agent Engine (Agent Runtime) in us-central1.

Run only AFTER ADC / IAM is fixed. Nothing here should be executed while the
deploy is blocked; this file is prepared so the deploy is one command.

--------------------------------------------------------------------------------
IMPORTANT — behavioral gap vs. the local demo (read before trusting the trace)
--------------------------------------------------------------------------------
Locally, `warroom.commander.run_war_room()` drives the agents with a *hand-written
control loop*: it runs triage, then per-round runs investigator + critic via
separate `Runner`s, parses `critic_verdict` JSON out of session state, and
decides itself when to break (critic accepted -> RESOLVED) or exhaust rounds
(-> FAILED). It also emits the PublicEventProjector events and builds a
`WarRoomResult`.

This script instead deploys `war_room_pipeline`, the *ADK-native* topology:

    SequentialAgent(war_room_commander)
      -> triage_agent
      -> LoopAgent(critique_loop, max_iterations=MAX_ITERATIONS)
           -> investigator_agent
           -> critic_agent

Deploying the pipeline directly is the correct thing for M3 (it proves
deploy -> managed session -> observable multi-agent trace), but its runtime
behavior differs from the local orchestration in three honest ways:

1. NO EARLY TERMINATION ON ACCEPTANCE. The LoopAgent stops only on
   `max_iterations` or on an explicit escalation action. `critic_agent` emits a
   JSON verdict as text but never raises an ADK escalation, so the deployed loop
   will run the FULL MAX_ITERATIONS every time instead of stopping the moment the
   Critic accepts. The "rejection changes the next action" story is still
   visible in the trace (investigator round 2 reacts to round-1 critique via
   session state), but the RESOLVED-vs-FAILED terminal decision that lives in
   run_war_room() is NOT reproduced here.
   -> Workaround for true early-stop (future, not required for M3): wrap the
      commander logic in a custom `BaseAgent` (or give critic_agent a tool that
      sets `actions.escalate = True` on acceptance) and deploy THAT instead of
      the raw SequentialAgent. Left out on purpose to keep M3 minimal.

2. NO PublicEventProjector EVENTS. The projector.emit(...) calls live in
   run_war_room(), not in the agents. The deployed pipeline produces ADK/GEAP
   trace spans and event authors (which is the observability proof M3 wants),
   but not the `agent-war-room.public-event.v1` stream. OpenAB-facing public
   events are an M4 concern.

3. read_lab_file IS A NO-OP REMOTELY. investigator's read_lab_file resolves a
   local filesystem path (parents[2]/incident-lab) that does not exist in the
   Agent Engine container. Remote investigation therefore relies on http_get +
   post_message against INCIDENT_LAB_URL (the Cloud Run incident-lab). This is
   fine for the controlled reproduction, which is POST /message based.

Model note: local agents hardcode gemini-3.5-flash (global-only). Agent Engine
runs in us-central1, so this script rewrites every LlmAgent in the tree to
gemini-2.5-flash (us-central1-compatible) before deploy.
"""
from __future__ import annotations

import os

# Point the (remote) investigator at the deployed incident-lab. Must be set
# BEFORE importing warroom.investigator, because SERVICE_URL is read at import
# time. It is ALSO passed as env_vars= to the deployed runtime below so the
# remote container resolves the same URL.
INCIDENT_LAB_URL = os.environ.get("INCIDENT_LAB_URL", "<incident-lab-cloud-run-url>")
os.environ.setdefault("INCIDENT_LAB_URL", INCIDENT_LAB_URL)
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"

import vertexai
from google.adk.agents import LlmAgent
from vertexai import agent_engines

try:
    from vertexai.preview.reasoning_engines import AdkApp
except Exception:  # noqa: BLE001  # SDK version drift
    from vertexai.agent_engines import AdkApp

# war_room_pipeline is the ADK-native SequentialAgent(triage -> loop(inv, critic)).
from warroom.commander import war_room_pipeline

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "<your-project>")
LOCATION = "us-central1"  # Agent Engine region; has the gemini-2.5 family.
STAGING = os.environ.get(
    "AGENT_ENGINE_STAGING_BUCKET",
    f"gs://{PROJECT}-agent-war-room-staging",
)
# us-central1-compatible model (local demo uses gemini-3.5-flash @ global only).
CENTRAL1_MODEL = os.environ.get("AGENT_ENGINE_MODEL", "gemini-2.5-flash")


def rewrite_models(agent: object, model: str, _seen: set[int] | None = None) -> int:
    """Recursively set `.model` on every LlmAgent in the tree. Returns count.

    Agents in the local package pin gemini-3.5-flash (global-only). Agent Engine
    is us-central1, so every leaf LlmAgent must be moved to a central1 model.
    """
    seen = _seen if _seen is not None else set()
    if id(agent) in seen:
        return 0
    seen.add(id(agent))

    count = 0
    if isinstance(agent, LlmAgent):
        try:
            agent.model = model  # pydantic field; assignable
            count += 1
        except Exception as error:  # noqa: BLE001
            print(f"!! could not set model on {getattr(agent, 'name', agent)}: {error}")

    for sub in getattr(agent, "sub_agents", None) or []:
        count += rewrite_models(sub, model, seen)
    return count


def main() -> None:
    rewritten = rewrite_models(war_room_pipeline, CENTRAL1_MODEL)
    print(f">>> rewrote {rewritten} LlmAgent(s) to model={CENTRAL1_MODEL}", flush=True)
    print(f">>> project={PROJECT} location={LOCATION} staging={STAGING}", flush=True)
    print(f">>> INCIDENT_LAB_URL={INCIDENT_LAB_URL}", flush=True)

    if "<your-project>" in PROJECT or "<incident-lab" in INCIDENT_LAB_URL:
        print(
            "!! Refusing to deploy: set GOOGLE_CLOUD_PROJECT and INCIDENT_LAB_URL "
            "first (see DEPLOY-M3.md).",
            flush=True,
        )
        raise SystemExit(2)

    vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING)

    app = AdkApp(agent=war_room_pipeline, enable_tracing=True)

    print(">>> deploying to Agent Engine (builds a container, ~5-10 min)...", flush=True)
    remote = agent_engines.create(
        agent_engine=app,
        requirements=["google-adk==2.6.2"],
        display_name="agent-war-room-full",
        description=(
            "COSCUP 2026 Debugging War Room — full pipeline "
            "(Triage -> Loop[Investigator, Critic]) (M3)"
        ),
        # Passed into the deployed runtime so the remote investigator resolves
        # the Cloud Run incident-lab and uses Vertex for models.
        env_vars={
            "INCIDENT_LAB_URL": INCIDENT_LAB_URL,
            "GOOGLE_GENAI_USE_VERTEXAI": "1",
        },
    )
    print("\n>>> DEPLOYED. resource_name:", remote.resource_name, flush=True)

    # Smoke query -> creates a managed session visible in the GEAP console.
    print("\n>>> smoke query...", flush=True)
    try:
        session = remote.create_session(user_id="coscup-demo")
        for ev in remote.stream_query(
            user_id="coscup-demo",
            session_id=session["id"],
            message="同一使用者在兩個 Discord threads 的對話內容互相污染",
        ):
            print(ev, flush=True)
    except Exception as error:  # noqa: BLE001
        print(f"query note: {type(error).__name__}: {error}", flush=True)

    print("\n>>> DONE. GEAP console → Agent Engine → agent-war-room-full", flush=True)


if __name__ == "__main__":
    main()
