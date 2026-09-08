export type SessionStatus = "ready" | "running" | "waiting_input" | "completed" | "failed" | "cancelled";
export interface SessionSummary {
  id: string; label: string; status: SessionStatus; created_at: string; updated_at: string;
}
export interface Message {
  id: string; session_id: string; position: number; role: "user" | "assistant" | "system";
  content: string; attachments: string[]; created_at: string;
}
export interface ToolEvent {
  id: string; session_id: string; position: number; run_id: string; call_id: string;
  tool_name: string; event_type: "started" | "completed" | "failed" | "cancelled";
  payload: Record<string, unknown>; created_at: string;
}
export interface SessionHistory extends SessionSummary { messages: Message[]; tool_events: ToolEvent[] }
export interface SessionApi {
  send: (id: string, messageId: string, content: string, urls?: string[]) => Promise<SessionHistory>;
  retry: (id: string) => Promise<SessionHistory>;
  list: () => Promise<SessionSummary[]>;
  get: (id: string) => Promise<SessionHistory>;
  create: (label: string) => Promise<SessionHistory>;
  delete: (id: string) => Promise<boolean>;
}
