# incident-lab

`incident-lab` is a zero-dependency Python 3.11 chat-session service for
fault-injection demonstrations. It models a small gateway that stores message
context in memory and returns the accumulated context with every reply.

## Architecture

- `server.py` provides the HTTP service and in-memory session store.
- `fault_store.py` owns persistent fault-state reads and writes.
- `state/fault.json` persists the selected mode across service restarts.
- `logs/service.log` records runtime request metadata and session-key clues.
- `incidents/session-collision/` contains reproduction material and ground truth.

Session context is volatile and resets when the service restarts or the fault
mode changes. Fault state remains persistent in its JSON file.

In `normal` mode, sessions are scoped by:

    user_id + channel_id + thread_id

In `session_collision` mode, the injected bug scopes sessions by:

    user_id

## Run

Requires Python 3.11 or a compatible newer Python 3 release.

    ./run.sh

The service listens on `127.0.0.1:8899` by default. Set
`INCIDENT_LAB_HOST=0.0.0.0` only when remote access is intentional.

## Endpoints

### `GET /health`

Returns service status and the active fault mode.

### `GET /fault`

Returns the active fault mode.

### `POST /fault`

Selects a mode and clears volatile sessions:

    curl -sS http://127.0.0.1:8899/fault \
      -H 'Content-Type: application/json' \
      -d '{"mode":"session_collision"}'

Valid modes are `normal` and `session_collision`.

### `POST /message`

Accepts a chat message:

    curl -sS http://127.0.0.1:8899/message \
      -H 'Content-Type: application/json' \
      -d '{
        "user_id":"user-1",
        "channel_id":"demo",
        "thread_id":"thread-a",
        "text":"hello"
      }'

The response includes `reply`, `context`, and `context_size`.

## Reproduce the incident

Start the service in one terminal:

    ./run.sh

Run the reproducer in another terminal:

    ./incidents/session-collision/reproduce.py

The reproducer enables `session_collision`, sends messages for one user to two
threads, and prints the response proving whether thread-alpha context appeared
in thread-beta.

Exit codes:

- `0`: contamination reproduced.
- `1`: no contamination found.
- `2`: request or protocol failure.

For a control run, restore normal mode and preserve it during reproduction:

    curl -sS http://127.0.0.1:8899/fault \
      -H 'Content-Type: application/json' \
      -d '{"mode":"normal"}'
    ./incidents/session-collision/reproduce.py --no-inject

The control run is expected to exit with code `1`.

## Trust boundary

Everything under `incidents/`, especially `ground-truth.json`, is evaluator
data. Production or agent-facing deployments must not mount or copy that
directory into the runtime visible to diagnostic agents. Agents may receive
service behavior, approved telemetry, and separately selected sample logs;
they must not receive ground truth. The runnable service does not read files
from `incidents/`.
