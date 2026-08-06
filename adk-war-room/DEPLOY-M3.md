# DEPLOY-M3 — Full 4-agent war room on GEAP Agent Engine

One-page runbook for deploying the full war room once ADC / IAM is fixed.

Current blocker: deploy is waiting on ADC (owner must fix the IAM /
Application Default Credentials so `gcloud auth application-default` and the
Agent Engine service identity work). Do **not** run any command below until
that is cleared — everything here is prepared, not executed.

## What gets deployed

1. **incident-lab** → Cloud Run (`us-central1`): the fault-injectable chat
   service the Investigator probes for the controlled two-thread reproduction.
2. **war_room_pipeline** → Agent Engine / Agent Runtime (`us-central1`):
   `SequentialAgent(triage → LoopAgent(investigator, critic))`, all LlmAgents
   rewritten to `gemini-2.5-flash` (us-central1-compatible; the local demo uses
   `gemini-3.5-flash`, which is global-only).

The Agent Engine investigator calls the Cloud Run incident-lab via the
`INCIDENT_LAB_URL` env var, so incident-lab must be deployed **first**.

> Read the behavioral-gap header in `deploy_full_agent_engine.py` before the
> demo: the deployed LoopAgent runs the full `MAX_ITERATIONS` (no early stop on
> Critic acceptance), emits no PublicEventProjector events, and `read_lab_file`
> is a no-op remotely. That is expected for M3.

## Prerequisites (verify once ADC is fixed)

```bash
gcloud auth application-default login          # or the owner-fixed ADC path
gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"

export GOOGLE_CLOUD_PROJECT="<your-project>"
export REGION="us-central1"

# Enable APIs (idempotent):
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  --project "${GOOGLE_CLOUD_PROJECT}"

# Staging bucket for Agent Engine (create if missing):
gsutil ls "gs://${GOOGLE_CLOUD_PROJECT}-agent-war-room-staging" 2>/dev/null \
  || gsutil mb -l "${REGION}" "gs://${GOOGLE_CLOUD_PROJECT}-agent-war-room-staging"
```

## Step 1 — Deploy incident-lab to Cloud Run

Full detail + smoke tests: `incident-lab/cloudrun-deploy.md`.

```bash
cd incident-lab
gcloud run deploy incident-lab \
  --source . \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 --cpu 1 --memory 256Mi \
  --min-instances 0 --max-instances 1
cd ..

export INCIDENT_LAB_URL="$(gcloud run services describe incident-lab \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${REGION}" \
  --format='value(status.url)')"
echo "INCIDENT_LAB_URL=${INCIDENT_LAB_URL}"

# Arm the injected bug for the demo:
curl -sS "${INCIDENT_LAB_URL}/fault" \
  -H 'Content-Type: application/json' -d '{"mode":"session_collision"}'
```

## Step 2 — Deploy the full pipeline to Agent Engine

`INCIDENT_LAB_URL` and `GOOGLE_CLOUD_PROJECT` must be exported (from Step 1).

```bash
cd adk-war-room
# Use the deploy venv if present, else any env with google-adk==2.6.2 + vertexai:
python3 deploy_full_agent_engine.py
```

The script:
- refuses to run until `GOOGLE_CLOUD_PROJECT` and `INCIDENT_LAB_URL` are real
  (guards against the `<your-project>` / `<incident-lab-...>` placeholders);
- rewrites every LlmAgent to `gemini-2.5-flash`;
- creates the Agent Engine, passing `INCIDENT_LAB_URL` as a runtime env var;
- runs a smoke `stream_query` that creates a managed session;
- prints `resource_name`.

## Step 3 — Verify

- GEAP console → **Agent Engine → agent-war-room-full**: confirm the deploy,
  open the smoke session, and inspect the trace — you should see the `triage`
  author, then repeated `investigator` / `critic` authors inside the loop, plus
  tool-call spans for `http_get` / `post_message` against the Cloud Run URL.
- Two concurrent sessions (M3 acceptance): create a second session with a
  different `user_id` and confirm isolation in the console.

## Teardown (after the demo)

```bash
# Agent Engine: delete via the console, or:
#   agent_engines.get("<resource_name>").delete(force=True)
gcloud run services delete incident-lab \
  --project "${GOOGLE_CLOUD_PROJECT}" --region "${REGION}" --quiet
```

## Overrides (env vars)

| Var | Default | Purpose |
|-----|---------|---------|
| `GOOGLE_CLOUD_PROJECT` | `<your-project>` | GCP project |
| `INCIDENT_LAB_URL` | placeholder | Cloud Run incident-lab URL (required) |
| `AGENT_ENGINE_MODEL` | `gemini-2.5-flash` | central1-compatible model |
| `AGENT_ENGINE_STAGING_BUCKET` | `gs://<project>-agent-war-room-staging` | build staging |
| `MAX_ITERATIONS` | `3` | critique loop bound (baked at import) |
