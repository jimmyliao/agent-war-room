"""Compare the war room's final diagnosis against the sealed ground truth."""

import json
import sys
from pathlib import Path

RUNS = Path(__file__).parent / "runs"
GT = Path(
    "/home/jimmyliao/workspace/agent-war-room/incident-lab/incidents/"
    "session-collision/ground-truth.json"
)


def main() -> None:
    run_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else sorted(p for p in RUNS.iterdir() if p.is_dir())[-1]
    )
    events = [
        json.loads(line)
        for line in (run_dir / "events.jsonl").read_text().splitlines()
    ]
    accepted = [e for e in events if e["type"] == "review.accepted"]
    rejected = [e for e in events if e["type"] == "review.rejected"]
    resolved = [e for e in events if e["type"] == "incident.resolved"]
    gt = json.loads(GT.read_text())

    print("=" * 62)
    print("🔍 INCIDENT REVEAL —", run_dir.name)
    print("=" * 62)
    print(f"Critic rejections : {len(rejected)}")
    print(f"Critic acceptance : {len(accepted)}")
    print(f"Resolved          : {bool(resolved)}")
    print("-" * 62)
    diagnosis = (accepted or resolved or [{}])[-1].get("summary", "(none)")
    print("Agent diagnosis   :", diagnosis[:220])
    print("-" * 62)
    print("Injected fault    :", gt.get("fault"))
    print("Expected diagnosis:", gt.get("expected_diagnosis"))
    match = "session" in diagnosis.lower() or "session_key" in diagnosis or "user_id" in diagnosis
    print("-" * 62)
    print("RESULT            :", "✅ MATCH" if match else "❌ MISMATCH")
    print("=" * 62)


if __name__ == "__main__":
    main()
