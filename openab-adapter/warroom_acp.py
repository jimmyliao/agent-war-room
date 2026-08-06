#!/usr/bin/env python3
"""warroom-acp — a case-specific ACP backend for OpenAB.

OpenAB (the OSS ACP broker) spawns this process and speaks the Agent Client
Protocol (ACP, https://agentclientprotocol.com) to it over stdio:

    Discord ──▶ OpenAB ──(ACP / newline-delimited JSON-RPC 2.0 on stdio)──▶ warroom_acp.py
                                                                              │
                                                                              ▼
                                                          run_war_room(symptom, projector)
                                                                              │
                                                                  public events (allowlisted)
                                                                              │
    Discord ◀── OpenAB ◀──(session/update: agent_message_chunk)──────────────┘

This is deliberately a *thin* adapter (see docs/SPEC.md §5.5). It does NOT
implement any agent orchestration — the ADK Incident Commander owns that. Its
only jobs are:

  1. Speak ACP to OpenAB (initialize / session.new / session.prompt / cancel).
  2. Turn one Discord user message (the incident symptom) into one War Room run.
  3. Project *only allowlisted public events* back to Discord, in order.

Ground-truth safety
-------------------
The only events that ever leave this process are the ones the War Room's own
``PublicEventProjector`` emits, and every one is re-checked against the exact
same allowlist (``ALLOWED_PUBLIC_TYPES``) before it is written to the ACP
channel. Hidden ground truth, private model reasoning, tool payloads and
credentials are never emitted by the projector and never touched here.

Two run modes (WARROOM_MODE)
----------------------------
  * ``replay`` (default): stream a curated public-event fixture line by line.
    This exercises the whole Discord → OpenAB → ACP → adapter → Discord path
    with NO GCP credentials and NO ADK/Vertex dependency. Use it to prove the
    wiring end to end. See NFR-6 (fixture-backed local learning path).
  * ``live``: import ``warroom.commander.run_war_room`` and run a real ADK
    incident in-process. Requires the ADK stack (google-adk), Vertex ADC for
    your own GCP project, and a reachable incident-lab. The public event
    contract streamed back to Discord is byte-for-byte the same as replay mode.

Transport note
--------------
stdout is the ACP channel and must carry *only* JSON-RPC messages. The War Room
projector and ADK libraries print progress to stdout, so while a live run is in
flight we point ``sys.stdout`` at stderr and write ACP frames through a private
handle captured at startup. All adapter logging goes to stderr.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# ACP transport constants (verified against @agentclientprotocol/sdk 0.25.1,
# the exact SDK the stock OpenAB ACP backends use).
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = 1  # schema/index.js: PROTOCOL_VERSION = 1

# Agent-side methods OpenAB (the client) calls on us. camelCase handler ->
# wire string, mirroring schema AGENT_METHODS.
M_INITIALIZE = "initialize"
M_AUTHENTICATE = "authenticate"
M_SESSION_NEW = "session/new"
M_SESSION_PROMPT = "session/prompt"
M_SESSION_CANCEL = "session/cancel"
M_SESSION_LOAD = "session/load"

# Client-side method we call on OpenAB to stream progress (CLIENT_METHODS).
M_SESSION_UPDATE = "session/update"

# The public-event allowlist — kept identical to
# adk-war-room/warroom/events.py ALLOWED_TYPES. Nothing outside this set is
# ever forwarded to Discord, in either mode.
ALLOWED_PUBLIC_TYPES = {
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

WARROOM_MODE = os.environ.get("WARROOM_MODE", "replay").strip().lower()
# Pace between streamed events (seconds) — keeps the Discord timeline readable.
REPLAY_PACE_SECONDS = float(os.environ.get("WARROOM_REPLAY_PACE", "0.8"))
# Curated fixture used by replay mode. Defaults to the canonical happy-path run.
_ADAPTER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _ADAPTER_DIR.parent
DEFAULT_FIXTURE = _REPO_ROOT / "adk-war-room" / "sample-run" / "events.jsonl"
FIXTURE_PATH = Path(os.environ.get("WARROOM_FIXTURE", str(DEFAULT_FIXTURE)))


def log(*args: Any) -> None:
    """Adapter logging — stderr only (stdout is the ACP channel)."""
    print("[warroom-acp]", *args, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Public-event formatting / sanitisation
# ---------------------------------------------------------------------------
def sanitize_public_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Return a minimal public-contract event, or None if not allowlisted.

    Defence in depth: even in replay mode we drop any line whose ``type`` is
    not in the allowlist, and we only copy the public-contract fields, so a
    tampered fixture cannot smuggle extra keys through to Discord.
    """
    event_type = raw.get("type")
    if event_type not in ALLOWED_PUBLIC_TYPES:
        return None
    summary = " ".join(str(raw.get("summary", "")).split())
    if len(summary) > 240:
        summary = summary[:237] + "..."
    return {
        "schema": "agent-war-room.public-event.v1",
        "incidentId": raw.get("incidentId"),
        "sessionId": raw.get("sessionId"),
        "eventId": raw.get("eventId") or str(uuid.uuid4()),
        "timestamp": raw.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "agent": raw.get("agent"),
        "type": event_type,
        "summary": summary,
        "progress": max(0, min(100, int(raw.get("progress", 0) or 0))),
    }


def format_event_line(event: dict[str, Any]) -> str:
    """One Discord-facing line, matching the console timeline style."""
    emoji = EMOJI.get(event["type"], "•")
    # Leading blank line separates each event into its own scannable block
    # (OpenAB concatenates streamed chunks into one Discord message).
    return (
        f"\n\n{emoji} `[{event['progress']:>3}%]` **{event['agent']}** · "
        f"`{event['type']}`\n{event['summary']}"
    )


# ---------------------------------------------------------------------------
# ACP JSON-RPC server over stdio (stdlib only)
# ---------------------------------------------------------------------------
class ACPConnection:
    """Newline-delimited JSON-RPC 2.0 over stdio, agent (backend) side."""

    def __init__(self, out_stream: Any) -> None:
        self._out = out_stream
        self._write_lock = asyncio.Lock()

    async def _write(self, message: dict[str, Any]) -> None:
        data = json.dumps(message, ensure_ascii=False) + "\n"
        async with self._write_lock:
            self._out.write(data)
            self._out.flush()

    async def respond(self, request_id: Any, result: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def respond_error(
        self, request_id: Any, code: int, message: str
    ) -> None:
        await self._write(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def session_update(self, session_id: str, update: dict[str, Any]) -> None:
        await self.notify(
            M_SESSION_UPDATE, {"sessionId": session_id, "update": update}
        )

    async def send_text(self, session_id: str, text: str) -> None:
        """Stream an agent message chunk (the Discord-visible output)."""
        await self.session_update(
            session_id,
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": text},
            },
        )


class WarRoomAgent:
    """ACP agent that bridges a Discord message to one War Room run."""

    def __init__(self, conn: ACPConnection) -> None:
        self.conn = conn
        # sessionId -> asyncio.Task of the in-flight prompt turn (for cancel).
        self._turns: dict[str, asyncio.Task] = {}
        # sessionId -> asyncio.Event set when a cancel arrives.
        self._cancelled: dict[str, asyncio.Event] = {}

    # -- lifecycle methods -------------------------------------------------
    async def initialize(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "agentCapabilities": {"loadSession": False},
            "authMethods": [],
        }

    async def authenticate(self, _params: dict[str, Any]) -> dict[str, Any]:
        # No credentials are handled at the ACP layer; live-mode auth (Vertex
        # ADC) is ambient in the process environment.
        return {}

    async def new_session(self, _params: dict[str, Any]) -> dict[str, Any]:
        session_id = uuid.uuid4().hex
        self._cancelled[session_id] = asyncio.Event()
        return {"sessionId": session_id}

    async def cancel(self, params: dict[str, Any]) -> None:
        session_id = params.get("sessionId")
        log(f"cancel requested for session {session_id}")
        ev = self._cancelled.get(session_id)
        if ev:
            ev.set()
        task = self._turns.get(session_id)
        if task and not task.done():
            task.cancel()

    async def prompt(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = params["sessionId"]
        symptom = self._extract_text(params.get("prompt", []))
        cancel_event = self._cancelled.setdefault(session_id, asyncio.Event())
        cancel_event.clear()

        if not symptom:
            await self.conn.send_text(
                session_id,
                "請描述事故症狀（incident symptom），我會召集 War Room 進行分診與蒐證。",
            )
            return {"stopReason": "end_turn"}

        log(f"prompt session={session_id} mode={WARROOM_MODE} symptom={symptom!r}")
        try:
            if WARROOM_MODE == "live":
                stop = await self._run_live(session_id, symptom, cancel_event)
            else:
                stop = await self._run_replay(session_id, symptom, cancel_event)
        except asyncio.CancelledError:
            return {"stopReason": "cancelled"}
        except Exception as error:  # noqa: BLE001 - surface, never crash the loop
            log(f"turn failed: {type(error).__name__}: {error}")
            await self.conn.send_text(
                session_id,
                f"💥 War Room 執行失敗：{type(error).__name__}: {error}",
            )
            return {"stopReason": "end_turn"}
        return {"stopReason": stop}

    # -- run modes ---------------------------------------------------------
    async def _run_replay(
        self, session_id: str, symptom: str, cancel_event: asyncio.Event
    ) -> str:
        """Stream the curated public-event fixture as the incident timeline."""
        if not FIXTURE_PATH.exists():
            await self.conn.send_text(
                session_id, f"找不到重播 fixture：{FIXTURE_PATH}"
            )
            return "end_turn"
        await self.conn.send_text(
            session_id,
            f"🚨 **War Room（replay 模式）** 已受理事故：\n> {symptom}\n"
            "以下為公開事件時間軸（僅推送 allowlist 內的公開事件）：",
        )
        with FIXTURE_PATH.open(encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                if cancel_event.is_set():
                    return "cancelled"
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event = sanitize_public_event(raw)
                if event is None:
                    continue  # dropped: not an allowlisted public event
                await self.conn.send_text(session_id, format_event_line(event))
                await asyncio.sleep(REPLAY_PACE_SECONDS)
        return "end_turn"

    async def _run_live(
        self, session_id: str, symptom: str, cancel_event: asyncio.Event
    ) -> str:
        """Run a real ADK incident and stream the projector's public events."""
        # Imported lazily so replay mode needs none of the ADK/Vertex stack.
        adk_root = _REPO_ROOT / "adk-war-room"
        if str(adk_root) not in sys.path:
            sys.path.insert(0, str(adk_root))
        from warroom.commander import new_session_id, run_war_room  # type: ignore
        from warroom.events import PublicEventProjector  # type: ignore

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        class StreamingProjector(PublicEventProjector):
            """Keeps the base allowlist + file logging, also fans out to ACP."""

            def emit(self, agent, event_type, summary, progress):  # type: ignore[override]
                event = super().emit(agent, event_type, summary, progress)
                # emit() runs inside this loop's thread during run_war_room.
                loop.call_soon_threadsafe(queue.put_nowait, event)
                return event

        incident_id = _make_incident_id(symptom)
        runs_root = Path(
            os.environ.get(
                "WARROOM_RUNS_DIR",
                str(Path(tempfile.gettempdir()) / "warroom-acp-runs"),
            )
        )
        projector = StreamingProjector(
            incident_id=incident_id,
            session_id=new_session_id(),
            runs_root=runs_root,
        )

        await self.conn.send_text(
            session_id,
            f"🚨 **War Room（live 模式）** 已建立事故 `{incident_id}`：\n> {symptom}",
        )

        # Consumer: drain the projector queue and stream each public event.
        done = asyncio.Event()

        async def drain() -> None:
            while not (done.is_set() and queue.empty()):
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                clean = sanitize_public_event(event)
                if clean is not None:
                    await self.conn.send_text(session_id, format_event_line(clean))

        drain_task = asyncio.create_task(drain())

        # The projector + ADK print to stdout; protect the ACP channel by
        # pointing sys.stdout at stderr for the duration of the run.
        saved_stdout = sys.stdout
        sys.stdout = sys.stderr
        try:
            result = await run_war_room(symptom, projector)
        finally:
            sys.stdout = saved_stdout
            done.set()
            await drain_task

        if cancel_event.is_set():
            return "cancelled"
        await self.conn.send_text(
            session_id,
            f"最終狀態：**{result.state}**（{result.iterations} 輪）。"
            "完整推理與 ground truth 僅保留於 trace，不對外推送。",
        )
        return "end_turn"

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _extract_text(blocks: list[dict[str, Any]]) -> str:
        import re

        parts = [
            str(b.get("text", ""))
            for b in blocks
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        text = "\n".join(p for p in parts if p)
        # OpenAB prepends a <sender_context>{...}</sender_context> block carrying
        # the user's Discord id/name/channel ids — strip it so it never reaches
        # the war room or gets echoed back into the public channel.
        text = re.sub(
            r"<sender_context>.*?</sender_context>", "", text, flags=re.DOTALL
        )
        return text.strip()


def _make_incident_id(symptom: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", symptom).strip("-")[:32]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"INC-{cleaned or 'WARROOM'}-{ts}"


# ---------------------------------------------------------------------------
# Dispatch loop
# ---------------------------------------------------------------------------
async def _dispatch(agent: WarRoomAgent, conn: ACPConnection, msg: dict[str, Any]) -> None:
    method = msg.get("method")
    request_id = msg.get("id")
    params = msg.get("params") or {}
    is_request = request_id is not None

    try:
        if method == M_INITIALIZE:
            await conn.respond(request_id, await agent.initialize(params))
        elif method == M_AUTHENTICATE:
            await conn.respond(request_id, await agent.authenticate(params))
        elif method == M_SESSION_NEW:
            await conn.respond(request_id, await agent.new_session(params))
        elif method == M_SESSION_PROMPT:
            # Long-running: run as its own task so session/cancel can be read
            # and dispatched concurrently.
            session_id = params.get("sessionId")

            async def run_turn() -> None:
                result = await agent.prompt(params)
                await conn.respond(request_id, result)

            task = asyncio.create_task(run_turn())
            if session_id:
                agent._turns[session_id] = task
        elif method == M_SESSION_CANCEL:
            await agent.cancel(params)  # notification, no response
        elif is_request:
            await conn.respond_error(request_id, -32601, f"method not found: {method}")
        else:
            log(f"ignoring unknown notification: {method}")
    except Exception as error:  # noqa: BLE001
        log(f"dispatch error for {method}: {type(error).__name__}: {error}")
        if is_request:
            await conn.respond_error(request_id, -32000, str(error))


async def main() -> int:
    # Capture the real stdout for ACP frames before anything can redirect it.
    acp_out = sys.stdout
    conn = ACPConnection(acp_out)
    agent = WarRoomAgent(conn)
    loop = asyncio.get_running_loop()
    log(f"started (mode={WARROOM_MODE}, fixture={FIXTURE_PATH})")

    # Read stdin line by line without blocking the loop.
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break  # EOF: OpenAB closed the pipe
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            log(f"dropping non-JSON line: {text[:120]!r}")
            continue
        asyncio.create_task(_dispatch(agent, conn, msg))

    log("stdin closed, exiting")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        raise SystemExit(0)
