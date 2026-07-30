#!/usr/bin/env python3
"""Reproduce cross-thread contamination against incident-lab."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any


def post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8899",
        help="incident-lab base URL",
    )
    parser.add_argument(
        "--no-inject",
        action="store_true",
        help="do not change the current fault mode",
    )
    args = parser.parse_args()

    suffix = uuid.uuid4().hex[:8]
    user_id = f"demo-user-{suffix}"
    marker_alpha = f"ALPHA-SECRET-{suffix}"
    marker_beta = f"BETA-PUBLIC-{suffix}"

    try:
        if not args.no_inject:
            fault = post_json(
                args.base_url,
                "/fault",
                {"mode": "session_collision"},
            )
            print(f"fault mode: {fault['mode']}")

        first = post_json(
            args.base_url,
            "/message",
            {
                "user_id": user_id,
                "channel_id": "coscup-demo",
                "thread_id": "thread-alpha",
                "text": marker_alpha,
            },
        )
        second = post_json(
            args.base_url,
            "/message",
            {
                "user_id": user_id,
                "channel_id": "coscup-demo",
                "thread_id": "thread-beta",
                "text": marker_beta,
            },
        )
    except (OSError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        print(f"request failed: {error}", file=sys.stderr)
        return 2

    print("thread-alpha response:")
    print(json.dumps(first, ensure_ascii=False, indent=2))
    print("thread-beta response:")
    print(json.dumps(second, ensure_ascii=False, indent=2))

    beta_context = second.get("context", [])
    contaminated = any(
        isinstance(item, dict)
        and item.get("thread_id") == "thread-alpha"
        and item.get("text") == marker_alpha
        for item in beta_context
    )

    if contaminated:
        print(
            "CROSS-THREAD CONTAMINATION REPRODUCED: "
            "thread-beta received thread-alpha context."
        )
        return 0

    print("NO CONTAMINATION: thread contexts remained isolated.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
