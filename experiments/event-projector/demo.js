import { readFile } from "node:fs/promises";
import { projectEvents } from "./projector.js";

const fixtureUrl = new URL("./fixtures/session-collision.events.json", import.meta.url);
const rawEvents = JSON.parse(await readFile(fixtureUrl, "utf8"));
const publicEvents = projectEvents(rawEvents);

for (const event of publicEvents) {
  const progress = Number.isFinite(event.progress) ? ` ${event.progress}%` : "";
  console.log(`[${event.agent}]${progress} ${event.summary}`);
}
