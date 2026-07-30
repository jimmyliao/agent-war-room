import test from "node:test";
import assert from "node:assert/strict";
import { projectEvent, projectEvents } from "./projector.js";

const baseEvent = {
  visibility: "public",
  incidentId: "INC-003",
  sessionId: "discord:channel-1:thread-9:user-4",
  eventId: "evt-1",
  timestamp: "2026-07-24T13:00:00Z",
  agent: "evidence_critic",
  type: "review.rejected",
  summary: "Controlled reproduction is missing.",
  progress: 65,
};

test("projects an allowlisted public event", () => {
  const projected = projectEvent(baseEvent);
  assert.equal(projected.schema, "agent-war-room.public-event.v1");
  assert.equal(projected.agent, "evidence_critic");
  assert.equal(projected.type, "review.rejected");
});

test("drops trace-only and unknown event types", () => {
  assert.equal(projectEvent({ ...baseEvent, visibility: "trace_only" }), null);
  assert.equal(projectEvent({ ...baseEvent, type: "model.private_reasoning" }), null);
});

test("redacts sensitive evidence recursively", () => {
  const projected = projectEvent({
    ...baseEvent,
    evidence: {
      path: "session_mapper.py:47",
      credentials: "do-not-leak",
      nested: { token: "also-secret" },
    },
  });

  assert.deepEqual(projected.evidence, {
    path: "session_mapper.py:47",
    credentials: "[REDACTED]",
    nested: { token: "[REDACTED]" },
  });
});

test("projects only valid events in a mixed stream", () => {
  const projected = projectEvents([
    baseEvent,
    { ...baseEvent, visibility: "trace_only", eventId: "evt-2" },
    { ...baseEvent, type: "incident.resolved", eventId: "evt-3" },
  ]);

  assert.equal(projected.length, 2);
  assert.deepEqual(
    projected.map((event) => event.eventId),
    ["evt-1", "evt-3"],
  );
});
