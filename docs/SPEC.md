# Agent War Room — System and Experiment Specification

Status: Draft v0.3
Repository: `agent-war-room`

## 1. Executive summary

Agent War Room is a teaching-oriented, reproducible multi-agent debugging
system. A user reports an incident from Discord. OpenAB delivers the message to
an ADK application hosted on Gemini Enterprise Agent Platform (GEAP). An ADK
Incident Commander coordinates triage and evidence review, while an
Antigravity managed agent performs open-ended investigation inside an isolated
sandbox. GEAP provides managed execution, sessions, interactions, and
observability.

The project exists to answer a practical question:

> When should developers use deterministic tools and workflows, when should
> they use ADK multi-agent orchestration, and when should they delegate an
> open-ended task to an autonomous Antigravity agent?

It deliberately avoids treating four personas or four Discord bots as proof of
a multi-agent system. Collaboration must be visible in the execution graph,
must change subsequent behavior, and must be verifiable against incident ground
truth.

The primary demonstration is a reproducible session-collision incident:
unrelated Discord threads belonging to the same user leak context because the
session key omits `channel_id` and `thread_id`. The initial diagnosis is
intentionally insufficient. An Evidence Critic rejects it and requests a
controlled two-thread reproduction. The Commander then starts a bounded second
investigation. Only after causal evidence exists is the incident marked
resolved.

## 2. Motivation

Debugging is used as the driving scenario because students and early-career
engineers frequently face:

- unfamiliar repositories;
- deployment failures that work locally;
- confusing logs and competing hypotheses;
- incomplete evidence;
- side projects that need a demonstrable, recoverable engineering process.

Debugging naturally exposes the difference between:

- deterministic tools;
- fixed workflows;
- dynamic agent routing;
- autonomous investigation;
- evidence review;
- human approval;
- runtime observability.

A successful final answer alone does not demonstrate production readiness,
orchestration, observability, or recovery. This project is designed so those
properties are visible and verifiable rather than assumed.

## 3. Design thesis

> Multi-agent expertise is not how many bots appear on screen. It is knowing
> where to place deterministic logic, autonomy, responsibility boundaries, and
> verification.

Supporting statement:

> OpenAB determines where the user enters. ADK determines how the application
> coordinates work. Antigravity handles open-ended autonomous investigation.
> GEAP determines where the system runs, preserves state, and becomes
> observable.

## 4. Terminology and decision framework

### 4.1 Tool

A deterministic capability with a clear input and output:

```text
fetch_logs(service, time_range)
run_reproduction(scenario)
compare_session_ids(thread_a, thread_b)
```

Use a tool when the system should execute a known operation rather than reason
about which operation is needed.

### 4.2 Workflow

A predetermined sequence or graph:

```text
collect -> normalize -> validate -> store
```

Use a workflow when the steps and ordering are known and reliability is more
important than dynamic planning.

### 4.3 Agent

An agent receives a goal and decides which permitted tools or next steps are
needed based on intermediate evidence.

Example:

> Identify the root cause of cross-thread context leakage using the supplied
> repository snapshot, sanitized logs, and reproduction tools.

### 4.4 Multi-agent system

Use multiple agents when there are meaningful differences in:

- responsibility;
- tool or data access;
- output contract;
- failure boundary;
- evaluation criteria;
- ability to reject or change another agent's next action.

Four separate prompts are not sufficient.

### 4.5 Multi-bot system

Multiple Discord identities may be useful for presentation or loosely coupled
handoff, but do not by themselves demonstrate application-level
multi-agent orchestration.

### 4.6 Skill

A reusable package of instructions, scripts, reference files, or operating
procedures that teaches an agent how to perform a repeatable domain task.

In this project, evidence-based debugging is a skill. It is not a separate
agent merely because it contains multiple steps.

## 5. Technology responsibilities

### 5.1 OpenAB

OpenAB is an existing OSS ACP broker used by the project, not developed inside
this repository.

Responsibilities:

- Discord ingress and outbound delivery;
- channel, thread, message, user, and attachment handling;
- one conversational entry point for the War Room;
- delivery of public progress events;
- approval interaction;
- ACP communication with the case-specific adapter.

OpenAB must not decide:

- which investigator to call;
- whether evidence is sufficient;
- whether to re-plan;
- whether the incident is resolved.

### 5.2 ADK

ADK owns application-level orchestration:

- agent definitions and responsibility boundaries;
- deterministic and dynamic routing;
- orchestration state;
- delegation;
- parallel evidence collection;
- critique and bounded re-investigation;
- stopping conditions;
- human approval checkpoints;
- structured public events.

ADK is selected instead of hand-written orchestration to provide an explicit,
testable agent application rather than scattered prompts and `if/else` logic.

### 5.3 Antigravity

Antigravity is used as the autonomous investigator through GEAP Managed Agents
API, not merely as the desktop IDE or local CLI.

Responsibilities:

- open-ended investigation;
- reading permitted files and artifacts;
- running diagnostic and reproduction scripts in a sandbox;
- using mounted debugging skills;
- searching approved sources when configured;
- producing a structured diagnosis artifact.

Antigravity does not own:

- incident lifecycle;
- final acceptance;
- unbounded remediation;
- access to hidden ground truth;
- production credentials.

### 5.4 GEAP

GEAP provides two complementary execution paths:

1. ADK custom-code orchestration on Agent Runtime.
2. Antigravity managed-code autonomy through Managed Agents API and
   Interactions API.

Responsibilities demonstrated:

- remote managed execution;
- sessions and interaction continuity;
- sandboxed autonomous investigation;
- streaming events;
- trace, log, latency, and tool-call observability;
- separation between development framework and managed runtime.

Managed Agents API and the Antigravity base agent are Preview/Pre-GA and are
used only with synthetic, non-sensitive data.

### 5.5 Case-specific adapter

The repository contains `warroom-acp`, a thin adapter:

```text
OpenAB ACP/stdin
    <->
warroom-acp
    <->
GEAP ADK streamQuery
```

Responsibilities:

- translate ACP messages into remote ADK queries;
- create or retrieve session mappings;
- translate public War Room events into OpenAB-compatible updates;
- preserve event IDs for idempotent delivery;
- deliver approval responses back to the Commander.

It must not implement agent orchestration.

## 6. System architecture

```text
Discord
   |
   v
OpenAB OSS
   | ACP / stdio JSON-RPC
   v
warroom-acp
   | GEAP streaming query
   v
ADK Incident Commander on Agent Runtime
   |
   +-- Triage Agent
   |
   +-- Evidence Critic
   |
   +-- Antigravity Investigator Adapter
           |
           v
       Managed Agents API / Interactions API
           |
           v
       Antigravity sandbox
           |
           +-- repository snapshot
           +-- sanitized logs
           +-- debugging skill
           +-- controlled diagnostic scripts

GEAP Observability receives execution traces, logs, latency, and tool events.
```

## 7. Agent model

### 7.1 Incident Commander

Type: ADK agent/orchestrator.

Inputs:

- incident request;
- current incident state;
- triage brief;
- diagnosis artifact;
- critic decision;
- approval decision.

Responsibilities:

- own the incident state machine;
- route based on suspected domains;
- select deterministic or autonomous work;
- start independent evidence tasks in parallel;
- enforce a bounded number of investigation rounds (default three, i.e. the
  Critic may reject up to twice before a terminal decision);
- ask the user for missing information;
- request approval before mutation;
- end as resolved, inconclusive, rejected, or failed.

The Commander must not mark an incident resolved without an accepted Critic
decision.

### 7.2 Triage Agent

Type: ADK specialist agent.

Responsibilities:

- normalize the user report;
- separate observed facts, claims, and assumptions;
- classify suspected domains;
- identify missing inputs;
- define required evidence;
- propose independent investigation branches.

Output contract:

```json
{
  "observedFacts": [],
  "assumptions": [],
  "suspectedDomains": [],
  "missingInputs": [],
  "requiredEvidence": [],
  "parallelBranches": [],
  "severity": "low|medium|high"
}
```

The Triage Agent is read-only.

### 7.3 Antigravity Investigator

Type: GEAP Managed Agent using the Antigravity harness.

Responsibilities:

- consume the triage brief;
- inspect allowed evidence sources;
- execute controlled experiments;
- maintain an evidence ledger;
- generate multiple hypotheses when evidence allows;
- produce a diagnosis artifact.

Output contract:

```json
{
  "observations": [],
  "hypothesesConsidered": [],
  "experiments": [],
  "evidence": [],
  "proposedRootCause": "",
  "proposedFix": "",
  "regressionTest": "",
  "remainingUncertainty": []
}
```

The Investigator must not:

- read the ground-truth file;
- access unapproved networks;
- use production credentials;
- apply a patch or redeploy without approval.

### 7.4 Evidence Critic

Type: ADK specialist agent.

Responsibilities:

- check whether evidence supports causation;
- reject diagnoses based only on correlation;
- confirm reproduction exists;
- confirm alternative hypotheses were addressed;
- require a regression test;
- produce an explicit accept/reject decision.

Output contract:

```json
{
  "accepted": false,
  "supportedClaims": [],
  "unsupportedClaims": [],
  "missingEvidence": [],
  "requestedAction": "",
  "confidence": 0.0
}
```

The Critic must not silently rewrite an Investigator diagnosis into an accepted
answer.

## 8. Orchestration design

### 8.1 Why the system is not a baton-pass pipeline

The system must not always execute:

```text
Triage -> Investigator -> Critic -> Commander
```

Instead, execution depends on evidence:

```text
                         +-- session mapping inspection --+
Incident -> Triage ----->+-- request trace comparison -----+--> Investigator
                         +-- memory configuration check ----+       |
                                                                   v
                                                                Critic
                                                                /    \
                                                          accept      reject
                                                            |           |
                                                          report      re-plan
```

### 8.2 Required orchestration patterns

#### Conditional routing

Examples:

- HTTP 403 routes to identity/runtime evidence.
- context leakage routes to session/routing evidence.
- timeout routes to logs/code/dependency latency.
- schema failure routes to contract/code evidence.

#### Parallel fan-out

Independent, read-only evidence tasks may execute concurrently.

#### Join and synthesis

The Investigator must associate every conclusion with evidence from completed
branches.

#### Critique loop

The Critic may reject once or twice. The requested action must be narrower than
the original investigation and identify exactly what is missing.

#### Human-in-the-loop

Mutating actions pause:

- patch application;
- redeployment;
- IAM changes;
- service restart;
- traffic changes.

#### Bounded termination

Maximum autonomous investigation rounds: 3 (the Critic may reject up to twice).
Configurable via `MAX_ITERATIONS`. A clean run typically resolves in 2 rounds.

Terminal states:

- `resolved`;
- `inconclusive`;
- `rejected_by_user`;
- `failed`;
- `cancelled`.

## 9. Incident state machine

```text
NEW
 |
 v
TRIAGING
 |
 +--> NEEDS_INPUT --------+
 |                        |
 v                        |
INVESTIGATING <-----------+
 |
 v
REVIEWING
 |       \
 |        +--> REINVESTIGATING --> REVIEWING
 |
 +--> AWAITING_APPROVAL --> REMEDIATING --> VERIFYING
 |
 +--> RESOLVED
 +--> INCONCLUSIVE
 +--> FAILED
 +--> CANCELLED
```

State transitions must be persisted and idempotent.

## 10. Primary incident: session collision

### 10.1 User-visible symptom

The same user opens two unrelated Discord threads. A response in Thread B
contains context from Thread A.

### 10.2 Hidden ground truth

The mapping key uses only `user_id`:

```text
session_key = user_id
```

Correct mapping:

```text
session_key = platform + channel_id + thread_id + user_id
```

### 10.3 Required evidence

Before accepting the diagnosis:

1. Two distinct thread IDs map to the same session ID before the fix.
2. The source/configuration responsible for mapping is identified.
3. A controlled reproduction demonstrates the visible leak.
4. After the fix, the threads map to different sessions.
5. A regression test fails before the fix and passes after it.

### 10.4 Intended narrative

1. Triage classifies the incident as session/routing/memory.
2. The Investigator finds that the key contains `user_id`.
3. The Investigator initially claims this is the root cause.
4. The Critic rejects the claim because no controlled two-thread reproduction
   exists.
5. The Commander requests a bounded second investigation.
6. The Investigator performs the reproduction.
7. The Critic accepts.
8. Ground truth is revealed and compared.

This rejection is the central proof that the agents affect each other's future
behavior.

## 11. Secondary incidents

Secondary incidents may be implemented after the primary scenario.

### 11.1 Permission denied

Symptom: local execution succeeds, remote agent receives HTTP 403.

Teaching points:

- runtime identity;
- local versus deployed credentials;
- least privilege;
- GEAP agent identity and IAM.

### 11.2 Async timeout

Symptom: request exceeds its deadline although the dependency is healthy.

Ground truth: blocking operation inside an asynchronous handler.

Teaching points:

- competing hypotheses;
- parallel evidence collection;
- trace latency;
- rejecting "increase the timeout" as an unsupported fix.

### 11.3 Schema drift

Symptom: tool response validation fails.

Teaching points:

- structured contracts;
- deterministic validation;
- why validation should be code/tool logic rather than another persona.

## 12. Session and concurrency model

### 12.1 Thread-to-session mapping

Every Discord incident thread maps to an isolated GEAP session.

Input key:

```text
platform + channel_id + thread_id + user_id
```

Stored mapping:

```json
{
  "openabSessionKey": "",
  "geapUserId": "",
  "geapSessionId": "",
  "antigravityInteractionId": "",
  "antigravityEnvironmentId": ""
}
```

### 12.2 Concurrent incidents

Multiple incidents may run concurrently:

```text
INC-001  investigating
INC-002  awaiting approval
INC-003  resolved
```

One incident waiting for approval must not block other sessions.

### 12.3 Shared-resource safety

Read-only operations may run concurrently.

Mutations require:

- resource lock;
- human approval;
- idempotency key;
- audit event;
- post-action verification.

## 13. User experience

### 13.1 Design decision

Use one Discord War Room bot, not four independent bots.

Reasons:

- avoids implying that visible identities define agents;
- reduces Discord credentials and deployment complexity;
- avoids bot-to-bot loops;
- keeps the user focused on the incident;
- preserves ADK as the actual orchestrator.

### 13.2 User-visible timeline

```text
INC-003 — Cross-thread context leakage

[Commander] Incident created.
[Triage] Session, routing, and memory evidence requested.
[Investigator] Session key uses user_id only.
[Critic] Rejected: controlled two-thread reproduction is missing.
[Commander] Re-investigation requested.
[Investigator] Two threads reproduce the same shared session ID.
[Critic] Accepted.
[Commander] Root cause confirmed.
```

### 13.3 Progress message

A single Discord message should be edited rather than sending every low-level
event:

```text
[x] Triage
[x] Initial investigation
[x] Evidence review
[x] Controlled reproduction
[x] Root cause confirmed
```

Separate messages are reserved for:

- delegation;
- important evidence;
- Critic accept/reject;
- approval request;
- final report.

### 13.4 User-visible versus trace-only information

Public:

- agent name;
- activity summary;
- evidence reference;
- progress;
- acceptance/rejection;
- approval request;
- final incident report.

Trace only:

- full tool payloads;
- sanitized detailed logs;
- latency and token metrics;
- framework events;
- retry metadata.

Never expose:

- chain-of-thought/private model reasoning;
- credentials or tokens;
- unredacted user data;
- hidden ground truth before evaluation;
- unsafe remediation commands.

## 14. Public event contract

Schema:

```text
agent-war-room.public-event.v1
```

Allowed event types:

- `incident.started`
- `agent.delegated`
- `investigation.progress`
- `evidence.found`
- `review.accepted`
- `review.rejected`
- `approval.required`
- `incident.resolved`
- `incident.failed`

Required fields:

```json
{
  "schema": "agent-war-room.public-event.v1",
  "incidentId": "INC-003",
  "sessionId": "...",
  "eventId": "...",
  "timestamp": "...",
  "agent": "evidence_critic",
  "type": "review.rejected",
  "summary": "Controlled reproduction is missing.",
  "progress": 65
}
```

Requirements:

- allowlist event types;
- require explicit `visibility=public`;
- recursively redact known secret fields;
- deduplicate on `eventId`;
- preserve ordering per incident;
- tolerate retry/replay;
- never infer a public summary from private reasoning.

## 15. Observability and proof

The system must prove the agents actually executed.

Evidence available:

- GEAP execution trace;
- ADK event `author`;
- delegation spans;
- Antigravity interaction;
- tool calls;
- critique and second investigation;
- latency per stage;
- number of tool/model calls;
- final ground-truth comparison.

A recorded replay should show:

```text
Discord timeline | GEAP execution trace
```

The public UI is not the source of truth for orchestration. The trace and event
log are.

## 16. Evaluation design

### 16.1 Primary metrics

- root-cause correctness;
- required-evidence completeness;
- unsupported-claim count;
- reproduction success;
- regression-test quality;
- time to diagnosis;
- model calls;
- tool calls;
- investigation rounds;
- event-delivery correctness.

### 16.2 Ground-truth evaluation

The evaluator compares:

- predicted category;
- predicted root cause;
- required evidence references;
- expected regression behavior.

Ground truth is isolated from the Investigator runtime.

### 16.3 Reference dataset

- one fully implemented primary incident;
- two secondary incident definitions;
- at least one intentionally insufficient first diagnosis;
- at least one concurrent-session isolation test.

### 16.4 Future comparison

Deferred experiment:

```text
ADK specialist team
versus
single Antigravity autonomous agent
```

Compare correctness, latency, cost, implementation effort, transparency, and
recovery behavior. This is future work.

## 17. Security and safety

### 17.1 Data

Use only:

- synthetic incident data;
- generated logs;
- public or purpose-built source code;
- non-sensitive test credentials represented by placeholders.

### 17.2 Antigravity sandbox

- network disabled by default;
- explicit allowlist if required;
- no production credentials;
- no access to ground truth;
- read-only source mount where possible;
- writable temporary workspace for experiments.

### 17.3 Remediation

Default mode is diagnosis-only.

Any mutation requires:

- proposed diff/action;
- explicit user approval;
- a demo-only target;
- idempotency key;
- rollback or reset path.

### 17.4 Preview disclosure

Managed Agents API and the Antigravity preview base agent are Preview/Pre-GA.
They must not be recommended for sensitive or commercial production workloads in
their current preview state.

## 18. Repository and publication

### 18.1 Repository structure

```text
agent-war-room/
├── incident-lab/         Reproducible fault scenarios and ground truth
├── adk-war-room/         ADK orchestration application
├── antigravity-agent/    Managed Agent configuration and debugging skill
├── openab-adapter/       Case-specific ACP/Discord integration
├── skills/               Reusable debugging skill
├── experiments/          Executable technical spikes
└── docs/                 Specification and architecture
```

OpenAB remains an external OSS dependency and reference deployment. Its source
is not copied into this repository.

### 18.2 Public material

- architecture and sequence diagrams;
- teaching-oriented ADK orchestration;
- case-specific ACP adapter;
- Antigravity API adapter;
- debugging skill;
- synthetic Incident Lab;
- evaluation rubric;
- sanitized deployment examples.

### 18.3 Private material (never published)

- customer data;
- real incident traces;
- production credentials;
- proprietary consulting runbooks;
- commercial risk policies;
- internal OpenAB configuration;
- customer connectors;
- production-only skills and datasets.

### 18.4 Licensing

- code and reusable examples: Apache-2.0;
- written documentation and diagrams: CC BY 4.0;
- third-party assets: retain and cite original licenses.

## 19. Functional requirements

### FR-1 Incident creation

Create an incident from a Discord thread with a unique incident ID.

### FR-2 Session isolation

Map each thread to an isolated GEAP session.

### FR-3 Structured triage

Produce a schema-valid triage brief.

### FR-4 Dynamic routing

Select investigation branches based on suspected domains.

### FR-5 Autonomous investigation

Invoke Antigravity with only approved sources, tools, and skills.

### FR-6 Evidence review

Accept or reject the diagnosis using explicit criteria.

### FR-7 Bounded re-investigation

Allow a bounded number of investigation rounds (default three).

### FR-8 Public progress

Project safe structured events to OpenAB/Discord.

### FR-9 Ground-truth comparison

Compare the accepted diagnosis with hidden incident ground truth.

### FR-10 Concurrent sessions

Demonstrate at least two isolated incident sessions.

### FR-11 Approval

Pause before any mutating action.

### FR-12 Reset

Restore the Incident Lab to a known state.

## 20. Non-functional requirements

### NFR-1 Reproducibility

The primary incident must be repeatable from documented commands and fixtures.

### NFR-2 Safety

No production data, credentials, or unapproved mutations.

### NFR-3 Observability

Every orchestration stage must have an event or trace span.

### NFR-4 Idempotency

Repeated event delivery must not duplicate Discord messages or actions.

### NFR-5 Explainability

Public summaries must reference evidence without exposing private reasoning.

### NFR-6 Portability

The repository must provide a fixture-backed local learning path even when a
user lacks GEAP Preview access.

### NFR-7 Reproducible evidence

A machine-readable event log and an isolated ground-truth comparison must exist
for the primary incident.

## 21. Implementation milestones

### M0 — Specification and event projector

- formal specification;
- event schema;
- redaction and allowlist tests;
- session-collision fixture.

### M1 — Local incident and orchestration

- runnable Incident Lab;
- deterministic session-collision reproduction;
- local ADK Commander, Triage, and Critic;
- fixture-backed Investigator adapter;
- critique loop test.

### M2 — Antigravity integration

- create Managed Agent configuration;
- mount debugging skill;
- call Interactions API;
- preserve interaction/environment IDs;
- parse structured diagnosis artifact;
- test ground-truth isolation.

### M3 — GEAP deployment

- deploy ADK application to Agent Runtime;
- remote streaming query;
- session persistence;
- trace and log capture;
- two concurrent sessions.

### M4 — OpenAB integration

- implement `warroom-acp`;
- thread/session mapping;
- public progress message;
- approval round trip;
- attachment/artifact delivery.

### M5 — Evaluation

- primary incident end-to-end evaluation;
- secondary incident summaries;
- metrics table;
- repository instructions.

## 22. Acceptance criteria

The reference build is accepted when:

1. A user can initiate the primary incident from Discord or replay the same
   event fixture locally.
2. The session-collision symptom is reproducible.
3. Triage output is schema-valid.
4. At least two independent evidence tasks can be represented or executed in
   parallel.
5. The initial unsupported diagnosis is rejected.
6. The second investigation produces controlled causal evidence.
7. The accepted diagnosis matches hidden ground truth.
8. Public events show the four responsibilities without revealing private
   reasoning.
9. GEAP trace proves the execution path.
10. Two incident sessions remain isolated.
11. All repository tests pass.

## 23. Risks and mitigations

### Antigravity Preview access or API changes

Mitigation:

- isolate the adapter;
- retain fixture-backed implementation;
- record the working cloud run early;
- pin documented API revision where supported.

### ADK-to-Antigravity integration complexity

Mitigation:

- expose Antigravity as one controlled Investigator adapter/tool;
- avoid nesting unbounded orchestrators;
- use a structured diagnosis contract.

### Multi-agent appears to be role-play

Mitigation:

- show Critic rejection changing the next action;
- show trace authors and tool evidence;
- compare with hidden ground truth.

### System appears to be a fixed sequential workflow

Mitigation:

- show conditional routing;
- use independent evidence branches;
- include a critique/re-plan loop;
- demonstrate another isolated session.

## 24. Implementation status (2026-08-06)

What is real (verified) vs. roadmap, with the RCAs that unblocked each.

### Real / verified
- **Local run (L0/L1/L2)** — `npm test`/`demo` (event projector), incident-lab
  reproduces the collision, `run_incident.py` resolves in 2 rounds via the
  critique loop. Tagged `v0.1.0`.
- **GEAP full 4-agent E2E** — `deploy_full_agent_engine.py` deploys
  `war_room_pipeline` (SequentialAgent: triage → LoopAgent[investigator,
  critic]) to Vertex Agent Engine (us-central1); investigator's FunctionTools
  reach the Cloud Run incident-lab and reproduce the collision in the cloud.
  Tagged `v0.2.0`. See `DEPLOY-M3.md`.
- **Antigravity investigator** — `antigravity-agent/investigator.py` calls the
  public Gemini **Interactions API** (`.../v1beta/interactions`, model
  `antigravity-preview-05-2026`), returning the 8-key diagnosis contract.
- **Cloud Trace** — `trace_run.py` (OTel exporter); spans verified in console.
- **OpenAB → Discord** — `openab-adapter/warroom_acp.py` runs as an OpenAB ACP
  backend, streaming the public-event timeline into Discord (replay verified).

### RCAs (gotchas that blocked deploys)
1. **Agent Engine "failed to start"** — `requirements` omitted
   `google-cloud-aiplatform[agent_engines]`; `AdkApp` is pickled by reference so
   the remote must `import vertexai` to unpickle → `ModuleNotFoundError:
   vertexai`. Fix: pin it in `requirements`. Also ship the local `warroom`
   package via `extra_packages`.
2. **GCS staging 403 on deploy** — ADC `quota_project_id` pointed at a project
   whose billing account was a closed trial; `x-goog-user-project` mismatch →
   403. Fix: `gcloud auth application-default set-quota-project <project>`.
3. **Region/model** — Agent Engine runs in us-central1, which only has the
   `gemini-2.5` family; the local demo uses `gemini-3.5-flash` (global-only).
   Deploy recursively rewrites every `LlmAgent.model` to `gemini-2.5-flash`.
4. **OpenAB backend needs python3** — official openab images have none; build
   `FROM ghcr.io/openabdev/openab:*-codex` + `apt install python3`.
5. **OpenAB `<sender_context>` injection** — OpenAB prepends a JSON block with
   the user's Discord id/name/channel to the prompt; `warroom_acp._extract_text`
   strips it (privacy + input hygiene). Streamed chunks concatenate into one
   Discord message, so each event is prefixed with a blank line.

### Roadmap (honest)
- **Conversational follow-up in Discord** — feasible (~0.5–1 day). The
  Antigravity agent does **not** support multi-turn (`Multiturn chat is not
  enabled`); use `gemini-3.5-flash` with `previous_interaction_id` (verified) +
  the investigator tools for interactive log/code Q&A. Live mode only.
- **Antigravity via GEAP-Vertex managed runtime** — the Interactions API path
  already covers this need; the managed path is optional.

### Ops note
- A borrowed bot ("Max with AGY") temporarily runs warroom-acp for demo
  recording; **restore by 2026-08-10**: `docker compose down && docker start
  openab-max-agy` (in `~/workspace/leapcore-cc/deploy-warroom/`). Deployed GEAP
  reasoning engine + Cloud Run incident-lab bill until torn down.
