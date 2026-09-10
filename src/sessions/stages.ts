import type { SessionHistory, ToolEvent } from "./types";
import { decodeError, errorMessages } from "../errors/messages";

export interface ToolStage {
  key: string;
  run: number;
  tool: string;
  state: ToolEvent["event_type"] | "unfinished";
  summary?: string;
}

function shortText(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return undefined;
  const text = value.trim();
  return text.length > 240 ? `${text.slice(0, 240)}…` : text;
}

function safeSummary(event: ToolEvent): string | undefined {
  // Display only fields explicitly intended for users, never arguments, raw
  // results, stack traces, provider messages or serialized payloads.
  if (event.event_type === "failed") {
    const error = event.payload.error;
    const mapped = decodeError(error);
    if (mapped) return errorMessages[mapped.code];
    return error && typeof error === "object" && !Array.isArray(error)
      ? shortText((error as Record<string, unknown>).user_message) : undefined;
  }
  if (event.event_type === "completed") return shortText(event.payload.summary);
  return undefined;
}

export function toolStages(history: SessionHistory): ToolStage[] {
  const calls = new Map<string, ToolEvent>();
  const runs = new Map<string, number>();
  let latestRun: string | undefined;
  for (const event of [...history.tool_events].sort((a, b) => a.position - b.position)) {
    if (!runs.has(event.run_id)) {
      runs.set(event.run_id, runs.size + 1);
      latestRun = event.run_id;
    }
    // JSON tuple avoids collisions when IDs themselves contain separators.
    calls.set(JSON.stringify([event.run_id, event.call_id]), event);
  }
  return [...calls.entries()].map(([key, event]) => ({
    key, run: runs.get(event.run_id)!, tool: event.tool_name,
    state: event.event_type === "started" && (history.status !== "running" || event.run_id !== latestRun)
      ? "unfinished" : event.event_type,
    summary: safeSummary(event),
  }));
}
