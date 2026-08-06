#!/usr/bin/env python3
"""Antigravity Investigator via the Gemini Interactions API.

This is the real (non-stub) autonomous-investigator path for the War Room. It
uses the public Interactions API (a single Gemini API key), NOT the GEAP/Vertex
managed-runtime path — the same `antigravity-preview-05-2026` agent is reachable
both ways, and the API-key path is the lighter one for prototyping.

Contract (SPEC §7.3): the investigator returns a structured diagnosis artifact.

Usage:
    export GEMINI_API_KEY=<your key>
    python investigator.py                 # runs the session-collision demo
    INVESTIGATOR_MODEL=antigravity-preview-05-2026 python investigator.py

Env:
    GEMINI_API_KEY       required
    INVESTIGATOR_MODEL   default gemini-3.5-flash; set to
                         antigravity-preview-05-2026 for the autonomous agent.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = os.environ.get("INVESTIGATOR_MODEL", "gemini-3.5-flash")

DIAGNOSIS_KEYS = (
    "observations",
    "hypothesesConsidered",
    "experiments",
    "evidence",
    "proposedRootCause",
    "proposedFix",
    "regressionTest",
    "remainingUncertainty",
)

SYSTEM_INSTRUCTION = (
    "You are the War Room Investigator. Given a triage brief and evidence, "
    "produce a diagnosis. Output ONLY a single JSON object with exactly these "
    "keys: " + ", ".join(DIAGNOSIS_KEYS) + ". No markdown, no code fence, no "
    "prose. Do not claim evidence you were not given. Only synthetic, "
    "non-sensitive data is in scope."
)


def _parse_json(text: str) -> dict:
    """Tolerant JSON extraction (handles fences / surrounding prose)."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.IGNORECASE | re.DOTALL)
    for cand in ([m.group(1)] if m else []) + [text, text[text.find("{"):] if "{" in text else text]:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            continue
    return {}


def investigate(
    triage_brief: dict,
    evidence_context: str = "",
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    timeout: int = 180,
) -> dict:
    """Run one investigation round. Returns diagnosis + metadata."""
    api_key = api_key or os.environ["GEMINI_API_KEY"]
    body = {
        "model": model,
        "input": (
            "Triage brief:\n"
            + json.dumps(triage_brief, ensure_ascii=False, indent=2)
            + "\n\nEvidence / context:\n"
            + (evidence_context or "(none provided; reason from the brief)")
            + "\n\nProduce the diagnosis JSON now."
        ),
        "system_instruction": SYSTEM_INSTRUCTION,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)

    if "error" in data:
        raise RuntimeError(f"interactions API error: {data['error']}")

    text = ""
    for step in data.get("steps", []):
        if step.get("type") == "model_output":
            for part in step.get("content", []):
                text += part.get("text", "") or ""

    diagnosis = _parse_json(text)
    return {
        "status": data.get("status"),
        "interaction_id": data.get("id"),
        "model": model,
        "total_tokens": data.get("usage", {}).get("total_tokens"),
        "diagnosis": diagnosis,
        "diagnosis_valid": all(k in diagnosis for k in DIAGNOSIS_KEYS),
        "raw_text": text,
    }


if __name__ == "__main__":
    demo_brief = {
        "suspected_domains": ["session state isolation", "routing", "memory"],
        "required_evidence": [
            "same user_id, two thread_ids controlled reproduction",
            "session-key generation source",
        ],
        "route": ["inspect session key", "reproduce cross-thread leak"],
    }
    demo_evidence = (
        "incident-lab in session_collision mode: session_key = user_id only "
        "(missing channel_id + thread_id). POST /message to two threads for one "
        "user shows thread-beta reply contains thread-alpha's marker."
    )
    result = investigate(demo_brief, demo_evidence)
    print(json.dumps(result, ensure_ascii=False, indent=2))
