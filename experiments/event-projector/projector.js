const PUBLIC_EVENT_TYPES = new Set([
  "incident.started",
  "agent.delegated",
  "investigation.progress",
  "evidence.found",
  "review.accepted",
  "review.rejected",
  "approval.required",
  "incident.resolved",
  "incident.failed",
]);

const REDACTED_KEYS = new Set([
  "chain_of_thought",
  "credentials",
  "raw_log",
  "secret",
  "token",
]);

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!value || typeof value !== "object") return value;

  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      REDACTED_KEYS.has(key.toLowerCase()) ? "[REDACTED]" : redact(item),
    ]),
  );
}

export function projectEvent(rawEvent) {
  if (!rawEvent || rawEvent.visibility !== "public") return null;
  if (!PUBLIC_EVENT_TYPES.has(rawEvent.type)) return null;
  if (!rawEvent.agent || !rawEvent.summary) return null;

  return {
    schema: "agent-war-room.public-event.v1",
    incidentId: rawEvent.incidentId,
    sessionId: rawEvent.sessionId,
    eventId: rawEvent.eventId,
    timestamp: rawEvent.timestamp,
    agent: rawEvent.agent,
    type: rawEvent.type,
    summary: rawEvent.summary,
    progress: rawEvent.progress,
    evidence: redact(rawEvent.evidence),
  };
}

export function projectEvents(rawEvents) {
  return rawEvents.map(projectEvent).filter(Boolean);
}
