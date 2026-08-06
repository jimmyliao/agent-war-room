# Sample run — canonical happy path

`events.jsonl` is a real `run_incident.py` output that reached `RESOLVED` in
two investigation rounds, demonstrating the critique loop:

    incident.started → triage → investigate → review.rejected
    → reinvestigate → investigate → review.accepted → incident.resolved

The `review.rejected` → `review.accepted` transition is the core proof that the
Critic changes the Investigator's next action. Live runs write to
`adk-war-room/runs/<incident_id>/` (git-ignored); this directory keeps one
curated example under version control.
