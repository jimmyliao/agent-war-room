# Deploy incident-lab to Cloud Run

The Investigator agent reaches this service through `INCIDENT_LAB_URL`, using
only `GET /health`, `GET /fault`, and `POST /message`. Deploying it to Cloud
Run gives the Agent-Engine-hosted war room a reachable endpoint for the
controlled two-thread reproduction.

> Do not run any of these until ADC / IAM is fixed. This is the prepared
> command sequence only.

## 0. Prerequisites

```bash
export GOOGLE_CLOUD_PROJECT="<your-project>"     # e.g. from `gcloud config get-value project`
export REGION="us-central1"                       # co-locate with Agent Engine
export SERVICE="incident-lab"
```

## 1. Build + deploy from source (Cloud Build, no local Docker needed)

`gcloud run deploy --source` builds the image with Cloud Build using the
`Dockerfile` in this directory, then deploys it.

```bash
cd incident-lab

gcloud run deploy "${SERVICE}" \
  --source . \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 256Mi \
  --min-instances 0 \
  --max-instances 1
```

Notes:
- `--port 8080` matches the container's `${PORT:-8080}` default; Cloud Run also
  injects `PORT`, so the two always agree.
- `--max-instances 1` keeps the in-memory session store coherent. The fault
  state and session context live in the container's ephemeral filesystem /
  process memory; more than one instance would split that state and break the
  reproduction's determinism.
- `--allow-unauthenticated` is fine for synthetic, non-sensitive demo data. The
  service exposes no secrets and no ground truth. Tighten to authenticated
  ingress if you want the agent to carry an identity token instead.

## 2. Capture the service URL

```bash
export INCIDENT_LAB_URL="$(gcloud run services describe "${SERVICE}" \
  --project "${GOOGLE_CLOUD_PROJECT}" \
  --region "${REGION}" \
  --format='value(status.url)')"
echo "${INCIDENT_LAB_URL}"
```

Feed `INCIDENT_LAB_URL` into the Agent Engine deploy (see
`adk-war-room/deploy_full_agent_engine.py`).

## 3. Smoke test

```bash
curl -sS "${INCIDENT_LAB_URL}/health"
# -> {"status":"ok","service":"incident-lab","fault_mode":"normal"}

# Arm the injected bug for the demo:
curl -sS "${INCIDENT_LAB_URL}/fault" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"session_collision"}'
```

## Behavior parity notes

- Fault state (`state/fault.json`) and volatile sessions reset whenever the
  Cloud Run instance is recycled (scale-to-zero, redeploy). Re-arm
  `session_collision` before a demo run.
- The container never mounts `incidents/` or `scenarios/`; the Investigator can
  therefore never read ground truth over this endpoint. Its `read_lab_file`
  tool is filesystem-local and is a no-op against the remote service — the
  remote reproduction relies on `POST /message` instead.
