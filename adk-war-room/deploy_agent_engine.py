#!/usr/bin/env python3
"""M3 spike: deploy the Triage agent to GEAP Agent Engine (Agent Runtime).

Proves the "deploy → managed session → observable in console" path. Full 4-agent
deploy additionally needs the incident-lab service co-deployed (roadmap).
"""
import os

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"

import vertexai
from google.adk.agents import LlmAgent

try:
    from vertexai.preview.reasoning_engines import AdkApp
except Exception:  # noqa
    from vertexai.agent_engines import AdkApp  # fallback across SDK versions
from vertexai import agent_engines

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project")
LOCATION = "us-central1"  # Agent Engine region (has gemini-2.5 family)
STAGING = os.environ.get("STAGING_BUCKET", f"gs://{PROJECT}-agent-war-room-staging")

vertexai.init(project=PROJECT, location=LOCATION, staging_bucket=STAGING)

triage = LlmAgent(
    name="triage_agent",
    model="gemini-2.5-flash",  # us-central1-compatible (local demo uses 3.5-flash@global)
    instruction=(
        "你是 ADK Debugging War Room 的 Triage Agent。根據使用者描述的 incident 症狀，"
        "輸出一個 JSON object（不可有 markdown/code fence/前言）："
        '{"suspected_domains":["..."],"required_evidence":["..."],"route":["..."]}. '
        "對跨 Discord thread 的污染，required_evidence 必須要求：同一 user、兩個不同 "
        "thread_id 的 controlled reproduction。不可聲稱尚未取得的證據已存在。"
    ),
    description="Classifies an incident into suspected domains + required evidence.",
)

app = AdkApp(agent=triage, enable_tracing=True)

print(">>> deploying to Agent Engine (this builds a container, ~5-10 min)...", flush=True)
remote = agent_engines.create(
    agent_engine=app,
    requirements=["google-adk==2.6.2"],
    display_name="agent-war-room-triage",
    description="COSCUP 2026 Debugging War Room — Triage agent (M3 spike)",
)
print("\n>>> DEPLOYED. resource_name:", remote.resource_name, flush=True)

# smoke query → creates a managed session visible in console
print("\n>>> smoke query...", flush=True)
try:
    session = remote.create_session(user_id="coscup-demo")
    for ev in remote.stream_query(
        user_id="coscup-demo",
        session_id=session["id"],
        message="同一使用者在兩個 Discord threads 的對話內容互相污染",
    ):
        print(ev, flush=True)
except Exception as e:  # noqa
    print(f"query note: {type(e).__name__}: {e}", flush=True)

print("\n>>> DONE. GEAP console → Agent Engine → agent-war-room-triage", flush=True)
