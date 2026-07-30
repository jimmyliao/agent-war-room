"""Persistent fault-state storage, isolated from service behavior."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

VALID_MODES = frozenset({"normal", "session_collision"})


class FaultStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.set_mode("normal")

    def get_mode(self) -> str:
        with self._lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                mode = data.get("mode")
            except (OSError, json.JSONDecodeError):
                mode = None

            if mode not in VALID_MODES:
                return "normal"
            return mode

    def set_mode(self, mode: str) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"unsupported fault mode: {mode}")

        payload = json.dumps({"mode": mode}, indent=2) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            fd, temporary_name = tempfile.mkstemp(
                prefix=".fault-",
                suffix=".json",
                dir=self.path.parent,
                text=True,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, self.path)
            finally:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
