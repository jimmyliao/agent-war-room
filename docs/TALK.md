# COSCUP 2026 Talk Plan

## Proposed title

**四個 Agents 如何一起抓 Bug？GEAP × ADK × Antigravity × OpenAB 實戰**

Subtitle:

**從可控 Orchestration 到 Autonomous Investigation**

## Audience

Students, recent graduates, and developers interested in Google technologies.
The talk assumes basic familiarity with APIs and cloud deployment, but no prior
ADK or GEAP experience.

## Promise

After 30 minutes, the audience should be able to:

1. Distinguish a tool, workflow, agent, multi-agent system, and multiple bots.
2. Explain the different responsibilities of OpenAB, ADK, Antigravity, and
   GEAP.
3. Recognize conditional routing, parallel fan-out, critique loops, and
   human-in-the-loop control.
4. Understand when a managed autonomous investigator is preferable to
   hand-written specialist agents.
5. Use structured events and traces to verify that multi-agent collaboration
   actually occurred.

## 30-minute run of show

### 00:00–03:00 — The challenge

- Show a Discord incident with cross-thread context leakage.
- Ask: "If four bots answer, is that already multi-agent?"
- State the thesis: visible characters are not responsibility boundaries.

### 03:00–07:00 — The architecture vocabulary

- Tool versus workflow versus agent versus multi-agent.
- Introduce the four responsibility layers:
  - OpenAB: channel delivery.
  - ADK: application orchestration.
  - Antigravity: autonomous investigation.
  - GEAP: managed execution and observability.

### 07:00–11:00 — Design the four-agent team

- Commander, Triage, Investigator, Critic.
- Explain why each boundary exists.
- Contrast a fixed baton-pass pipeline with the execution graph.

### 11:00–18:00 — Recorded incident replay

- Trigger the session-collision scenario.
- Triage creates an evidence brief.
- Independent evidence collection runs.
- Antigravity produces an initial diagnosis.
- Critic rejects it due to missing reproduction evidence.
- Commander requests a second investigation.
- Root cause is confirmed and compared with hidden ground truth.

### 18:00–22:00 — Read the implementation

- ADK orchestration and stopping conditions.
- Antigravity skill and sandbox configuration.
- Public event projector and safe Discord progress.

### 22:00–26:00 — Prove what happened

- Show GEAP execution trace and agent authors.
- Show latency, tool calls, and the critique loop.
- Show a second isolated session to address concurrency.

### 26:00–29:00 — Engineering trade-offs

- Why not use only one autonomous Antigravity agent?
- Why not make every step an ADK agent?
- Preview limitations and production safety boundaries.

### 29:00–30:00 — Takeaways and repository

- Repeat the five takeaways.
- Show the repository QR code and reproducibility levels.

## Recorded demo guidance

- Use a side-by-side view: Discord timeline on the left, execution trace on the
  right.
- Show real cloud execution but remove idle waiting time.
- Display the actual unedited runtime duration.
- Keep an unedited recording and machine-readable event log in the repository.
- Never show private reasoning, credentials, or unredacted production data.

