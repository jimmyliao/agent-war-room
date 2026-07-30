# Architecture

## Runtime view

```text
Discord
   |
   v
OpenAB OSS deployment
   | ACP / stdio JSON-RPC
   v
warroom-acp
   | GEAP stream query
   v
ADK Incident Commander on Agent Runtime
   +-- Triage Agent
   +-- Evidence Critic
   +-- Antigravity adapter
          |
          v
      Managed Agents API / Interactions API
          |
          v
      Antigravity Investigator sandbox
```

## Session mapping

```text
OpenAB key:
  platform + channel_id + thread_id + user_id

maps to:
  GEAP user_id + session_id

and optionally:
  Antigravity interaction_id + environment_id
```

The mapping must never use `user_id` alone.

## Visibility model

```text
Raw ADK and Antigravity events
              |
              v
       Event Projector
          /       \
         v         v
 Public events   Trace-only events
 Discord        GEAP observability
```

The projector is a security and user-experience boundary, not merely a
formatter.

## Concurrency model

- Each incident thread owns an isolated GEAP session.
- Read-only evidence collection can run concurrently.
- Mutating actions require approval and a resource lock.
- Each action carries an idempotency key.
- An incident waiting for approval must not block other incident sessions.

