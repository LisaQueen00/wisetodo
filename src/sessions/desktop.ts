import { invoke } from "@tauri-apps/api/core";
import type { SessionApi, SessionHistory, SessionSummary } from "./types";

function object(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function summary(value: unknown): value is SessionSummary {
  return object(value) && typeof value.id === "string" && typeof value.label === "string"
    && typeof value.status === "string" && ["ready", "running", "waiting_input", "completed", "failed", "cancelled"].includes(value.status)
    && typeof value.created_at === "string" && typeof value.updated_at === "string";
}
function row(value: unknown, sessionId: string): value is Record<string, unknown> {
  return object(value) && typeof value.id === "string" && value.session_id === sessionId
    && typeof value.created_at === "string" && typeof value.position === "number"
    && Number.isSafeInteger(value.position) && value.position >= 0;
}
function history(result: unknown): SessionHistory {
  if (!object(result) || !summary(result.session)) throw new Error("Invalid Session response");
  const value = result.session as SessionSummary & Record<string, unknown>;
  if (!Array.isArray(value.messages) || !value.messages.every((message: unknown) => row(message, value.id)
    && ["user", "assistant", "system"].includes(String(message.role)) && typeof message.content === "string"
    && Array.isArray(message.attachments) && message.attachments.every((path: unknown) => typeof path === "string"))
    || !Array.isArray(value.tool_events) || !value.tool_events.every((event: unknown) => row(event, value.id)
      && typeof event.run_id === "string" && typeof event.call_id === "string" && typeof event.tool_name === "string"
      && ["started", "completed", "failed", "cancelled"].includes(String(event.event_type)) && object(event.payload))) {
    throw new Error("Invalid Session history");
  }
  return value as unknown as SessionHistory;
}
export const desktopSessionApi: SessionApi = {
  async send(sessionId, messageId, content, urls = []) {
    const result = history(await invoke("sessions_send", { sessionId, message: { message_id: messageId, content, ...(urls.length ? { urls } : {}) } }));
    if (result.id !== sessionId) throw new Error("Mismatched Session ID");
    return result;
  },
  async retry(sessionId) {
    const result = history(await invoke("sessions_retry", { sessionId }));
    if (result.id !== sessionId) throw new Error("Mismatched Session ID");
    return result;
  },
  async list() {
    const result = await invoke<unknown>("sessions_list");
    if (!object(result) || !Array.isArray(result.sessions) || !result.sessions.every(summary)) {
      throw new Error("Invalid Session list");
    }
    return result.sessions;
  },
  async get(sessionId) {
    const result = history(await invoke("sessions_get", { sessionId }));
    if (result.id !== sessionId) throw new Error("Mismatched Session ID");
    return result;
  },
  async create(label) { return history(await invoke("sessions_create", { label })); },
  async delete(sessionId) {
    const result = await invoke<unknown>("sessions_delete", { sessionId });
    if (!object(result) || typeof result.deleted !== "boolean") throw new Error("Invalid Session deletion");
    return result.deleted;
  },
};
