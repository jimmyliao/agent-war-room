# OpenAB Adapter — `warroom-acp`

The COSCUP demo uses the existing OpenAB OSS deployment as the Discord/ACP
broker. This directory contains `warroom_acp.py`, a case-specific ACP backend
that OpenAB spawns as a subprocess. It:

1. Accepts ACP messages from OpenAB over stdio (newline-delimited JSON-RPC 2.0).
2. Maps one Discord message to one War Room incident run.
3. Calls the ADK War Room (`run_war_room`) — or replays a curated fixture.
4. Projects **only allowlisted public events** back to Discord.

OpenAB itself is not copied or modified in this repository. `warroom-acp` is the
peer of the stock ACP backends (e.g. `codex-acp`) — same ACP wire contract,
different `[agent].command`.

## What it speaks (verified against the ACP SDK OpenAB ships, v0.25.1)

| Incoming (OpenAB → adapter) | Handling |
| --- | --- |
| `initialize` | returns `{ protocolVersion: 1, agentCapabilities: { loadSession: false } }` |
| `authenticate` | returns `{}` (no credentials handled at the ACP layer) |
| `session/new` | returns a fresh `sessionId` |
| `session/prompt` | runs the incident, streams progress, returns a `stopReason` |
| `session/cancel` | aborts the in-flight turn → `stopReason: "cancelled"` |

Outgoing (adapter → OpenAB): `session/update` notifications carrying
`agent_message_chunk` text — one Discord-visible line per public event.

Transport is newline-delimited JSON-RPC 2.0 on stdio. stdout carries **only**
ACP frames; all adapter logging and (in live mode) the War Room's own console
output go to stderr.

## Two run modes (`WARROOM_MODE`)

- **`replay`** (default) — streams the curated public-event fixture
  (`../adk-war-room/sample-run/events.jsonl`) as the incident timeline. Needs
  **no GCP credentials and no ADK/Vertex dependency**, so it exercises the whole
  Discord → OpenAB → ACP → adapter → Discord path on its own. This is the
  fixture-backed path from spec NFR-6.
- **`live`** — imports `warroom.commander.run_war_room` and runs a real ADK
  incident in-process. Requires the ADK stack (`google-adk`), Vertex ADC for
  your own GCP project, and a reachable incident-lab. The public-event contract
  streamed to Discord is identical to replay mode.

## Ground-truth boundary

The only events that leave the process are the ones the War Room's own
`PublicEventProjector` emits, and every one is re-checked here against the exact
same allowlist as `adk-war-room/warroom/events.py` (`ALLOWED_PUBLIC_TYPES`, 9
types) before it is written to the ACP channel. `sanitize_public_event()` also
copies **only** the public-contract fields, so hidden ground truth, tool
payloads, credentials, or extra keys cannot be smuggled to Discord — even from a
tampered fixture. Hidden ground truth is never read by this adapter.

## Local smoke test (no Discord, no GCP)

Drive it exactly the way OpenAB would:

```bash
cd openab-adapter
WARROOM_MODE=replay WARROOM_REPLAY_PACE=0 python3 - <<'PY'
import json, subprocess, sys, threading, time, os
p = subprocess.Popen([sys.executable, "warroom_acp.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
    env={**os.environ, "WARROOM_MODE": "replay", "WARROOM_REPLAY_PACE": "0"})
send = lambda o: (p.stdin.write(json.dumps(o) + "\n"), p.stdin.flush())
threading.Thread(target=lambda: [print(l.strip()) for l in p.stdout], daemon=True).start()
send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}); time.sleep(.3)
send({"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/tmp","mcpServers":[]}}); time.sleep(.3)
send({"jsonrpc":"2.0","id":3,"method":"session/prompt",
      "params":{"sessionId":"S","prompt":[{"type":"text","text":"兩個 thread 對話互相污染"}]}})
time.sleep(2); p.terminate()
PY
```

Expected: an `initialize` result with `protocolVersion: 1`, a `session/new`
result, a stream of `session/update` chunks (`incident.started` → … →
`incident.resolved`), then `{"stopReason":"end_turn"}`.

## Wiring it as a new OpenAB deploy

Create a sibling deploy directory next to the existing OpenAB bots (the same
layout they use: `config.toml` bind-mounted to `/etc/openab/config.toml`, plus
`passwd.overlay` / `group.overlay` / `home-scratch` for the uid/gid overlay).
Only the `[agent]` block differs from a stock bot — it points at this adapter
instead of a stock ACP backend.

### `config.toml` template

Tokens/IDs are `${...}` placeholders resolved from the deploy's env file — never
commit real values.

```toml
[discord]
bot_token = "${DISCORD_BOT_TOKEN}"
allow_all_channels = true
allowed_users = ["${DISCORD_USER_ID}"]
allow_bot_messages = "mentions"
allow_user_messages = "multibot-mentions"
allow_dm = true

[ambient]
enabled = true
flush_interval_seconds = 20

[ambient.discord]
channels = ["${WARROOM_CHANNEL_ID}"]

[agent]
# warroom-acp is stdlib-only in replay mode, so python3 is the whole runtime.
command = "python3"
args = ["${ADAPTER_DIR}/warroom_acp.py"]
working_dir = "${ADAPTER_DIR}"
# OpenAB runs the backend under env_clear(): every var the adapter needs must
# be listed here explicitly, or it will not reach the subprocess.
env = { WARROOM_MODE = "replay", WARROOM_REPLAY_PACE = "0.8" }
# --- live mode instead of replay: swap the env block for ---
# env = { WARROOM_MODE = "live", GOOGLE_GENAI_USE_VERTEXAI = "1", \
#         GOOGLE_CLOUD_PROJECT = "${GCP_PROJECT}", GOOGLE_CLOUD_LOCATION = "global", \
#         INCIDENT_LAB_URL = "${INCIDENT_LAB_URL}", MAX_ITERATIONS = "3" }

[pool]
max_sessions = 3
session_ttl_hours = 24
prompt_hard_timeout_secs = 1800

[reactions]
enabled = true
remove_after_reply = false

[markdown]
tables = "code"
```

### `compose.yaml` template

Mirrors the stock OpenAB bots. `${ADAPTER_DIR}` is the host path to this repo's
`openab-adapter/`; mount it (and, for live mode, the `adk-war-room/` tree) into
the container at the same path so `args` resolves.

```yaml
services:
  warroom:
    image: ${OPENAB_IMAGE}          # e.g. ghcr.io/openabdev/openab:<tag>
    container_name: openab-warroom
    restart: unless-stopped
    user: "${HOST_UID}:${HOST_GID}" # match host uid/gid (see below)
    environment:
      - HOME=${CONTAINER_HOME}
    env_file:
      - warroom.env                 # DISCORD_BOT_TOKEN, DISCORD_USER_ID, ... (chmod 600)
    volumes:
      - ./passwd.overlay:/etc/passwd:ro
      - ./group.overlay:/etc/group:ro
      - ./home-scratch:${CONTAINER_HOME}
      - ./config.toml:/etc/openab/config.toml:ro
      - ${ADAPTER_DIR}:${ADAPTER_DIR}          # the adapter
      - ${REPO_DIR}:${REPO_DIR}:ro             # live mode: adk-war-room + fixture
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    init: false
```

> **uid/gid + `/etc/passwd` overlay:** OpenAB backends fail silently (blank
> replies, exit 0) if the container uid has no `/etc/passwd` entry, or if `HOME`
> is not writable. Reuse the exact `passwd.overlay` / `group.overlay` /
> `home-scratch` pattern from an existing working OpenAB deploy — do not
> hand-roll it. This is an OpenAB deployment gotcha, not a `warroom-acp` one.

## Status: what runs now vs. what needs Jimmy

| Piece | State |
| --- | --- |
| ACP wire protocol (initialize / session.new / session.prompt / cancel / session.update) | ✅ Implemented and smoke-tested against the same SDK OpenAB ships |
| Replay mode — full public-event timeline streamed as ACP chunks | ✅ Runs standalone, no GCP, no ADK |
| Allowlist enforcement + field-strip + parity with `events.py` | ✅ Unit-tested |
| `session/cancel` → `stopReason: cancelled` mid-stream | ✅ Tested |
| Live mode — in-process `run_war_room`, streaming projector | ✅ Coded; needs `google-adk` + Vertex ADC + running incident-lab to actually run (unverified here — no GCP creds in this environment) |
| **End-to-end via real Discord** | ⛔ **Jimmy only** — needs a real `DISCORD_BOT_TOKEN` + bot user in the OpenAB server. Not runnable/committable from here. |

### The one step left for E2E (Jimmy)

1. Create/register a Discord bot user and channel for the War Room.
2. Make a `deploy-warroom/` directory from the templates above; fill
   `warroom.env` with the real `DISCORD_BOT_TOKEN` / `DISCORD_USER_ID` /
   `WARROOM_CHANNEL_ID` (and, for live mode, `GCP_PROJECT` + `INCIDENT_LAB_URL`),
   `chmod 600 warroom.env`.
3. Copy the `passwd.overlay` / `group.overlay` / `home-scratch` overlay from an
   existing working OpenAB deploy so the uid/gid + `HOME` boundary is correct.
4. `docker compose up -d`, then message the bot in its channel. Replay mode
   proves the full path with zero cloud dependencies; flip `WARROOM_MODE=live`
   once the ADK/Vertex/incident-lab side is up.
