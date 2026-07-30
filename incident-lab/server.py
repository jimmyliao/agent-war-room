#!/usr/bin/env python3
"""Minimal fault-injectable chat-session service."""

from __future__ import annotations

import argparse
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fault_store import FaultStore, VALID_MODES

ROOT = Path(__file__).resolve().parent
FAULT_STORE = FaultStore(ROOT / "state" / "fault.json")
SESSIONS: dict[str, list[dict[str, str]]] = {}
SESSIONS_LOCK = threading.Lock()


def configure_logging() -> None:
    log_path = ROOT / "logs" / "service.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s level=%(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def session_key(
    mode: str,
    user_id: str,
    channel_id: str,
    thread_id: str,
) -> str:
    if mode == "session_collision":
        return user_id
    return json.dumps(
        [user_id, channel_id, thread_id],
        ensure_ascii=False,
        separators=(",", ":"),
    )


class IncidentLabHandler(BaseHTTPRequestHandler):
    server_version = "incident-lab/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        logging.info(
            "remote=%s http=%s",
            self.client_address[0],
            format % args,
        )

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            raise ValueError("Content-Type must be application/json")

        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")

        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("invalid Content-Length") from error

        if length < 0 or length > 64 * 1024:
            raise ValueError("request body is too large")

        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("request body must be valid JSON") from error

        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _path(self) -> str:
        return urlsplit(self.path).path

    def do_GET(self) -> None:
        path = self._path()
        if path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "incident-lab",
                    "fault_mode": FAULT_STORE.get_mode(),
                },
            )
            return

        if path == "/fault":
            self._send_json(200, {"mode": FAULT_STORE.get_mode()})
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return

        path = self._path()
        if path == "/fault":
            self._set_fault(payload)
            return

        if path == "/message":
            self._post_message(payload)
            return

        self._send_json(404, {"error": "not found"})

    def _set_fault(self, payload: dict[str, Any]) -> None:
        mode = payload.get("mode")
        if mode not in VALID_MODES:
            self._send_json(
                400,
                {
                    "error": "mode must be normal or session_collision",
                    "valid_modes": sorted(VALID_MODES),
                },
            )
            return

        old_mode = FAULT_STORE.get_mode()
        FAULT_STORE.set_mode(mode)

        # Reset volatile context to keep demonstrations deterministic.
        with SESSIONS_LOCK:
            SESSIONS.clear()

        logging.warning(
            "event=fault_changed old_mode=%s new_mode=%s sessions_cleared=true",
            old_mode,
            mode,
        )
        self._send_json(200, {"mode": mode})

    def _post_message(self, payload: dict[str, Any]) -> None:
        required = ("user_id", "channel_id", "thread_id", "text")
        invalid = [
            field
            for field in required
            if not isinstance(payload.get(field), str) or not payload[field]
        ]
        if invalid:
            self._send_json(
                400,
                {
                    "error": "all fields must be non-empty strings",
                    "invalid_fields": invalid,
                },
            )
            return

        user_id = payload["user_id"]
        channel_id = payload["channel_id"]
        thread_id = payload["thread_id"]
        text = payload["text"]
        mode = FAULT_STORE.get_mode()
        key = session_key(mode, user_id, channel_id, thread_id)

        entry = {
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_id": thread_id,
            "text": text,
        }
        with SESSIONS_LOCK:
            context = SESSIONS.setdefault(key, [])
            context.append(entry)
            context_snapshot = [item.copy() for item in context]

        logging.info(
            "event=message mode=%s session_key=%s user_id=%s channel_id=%s "
            "thread_id=%s context_size=%d",
            mode,
            json.dumps(key, ensure_ascii=False),
            json.dumps(user_id, ensure_ascii=False),
            json.dumps(channel_id, ensure_ascii=False),
            json.dumps(thread_id, ensure_ascii=False),
            len(context_snapshot),
        )

        visible_context = [
            {
                "channel_id": item["channel_id"],
                "thread_id": item["thread_id"],
                "text": item["text"],
            }
            for item in context_snapshot
        ]
        summary = " | ".join(
            f'{item["thread_id"]}: {item["text"]}'
            for item in context_snapshot
        )

        self._send_json(
            200,
            {
                "reply": f"Context: {summary}",
                "context": visible_context,
                "context_size": len(visible_context),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()

    configure_logging()
    server = ThreadingHTTPServer((args.host, args.port), IncidentLabHandler)
    logging.info(
        "event=service_started host=%s port=%d pid=%d",
        args.host,
        args.port,
        __import__("os").getpid(),
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        logging.info("event=service_stopped timestamp=%d", int(time.time()))


if __name__ == "__main__":
    main()
