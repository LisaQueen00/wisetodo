// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { SessionStages } from "./SessionStages";
import { toolStages } from "./stages";
import type { SessionHistory, SessionStatus, ToolEvent } from "./types";

afterEach(cleanup);
const base: SessionHistory = { id: "session", label: "Read", status: "ready", created_at: "date", updated_at: "date", messages: [], tool_events: [] };
function event(position: number, fields: Partial<ToolEvent> = {}): ToolEvent {
  return { id: String(position), session_id: "session", position, run_id: "run1", call_id: "call1",
    tool_name: "parse_pdf", event_type: "started", payload: {}, created_at: "date", ...fields };
}

it.each<[SessionStatus, string, string]>([
  ["ready", "progress", "等待开始"], ["running", "progress", "执行中"],
  ["waiting_input", "progress", "等待补充输入"], ["completed", "result", "会话已完成"],
  ["failed", "error", "执行失败"], ["cancelled", "progress", "执行已停止"],
])("renders %s as a truthful %s snapshot", (status, kind, title) => {
  render(<SessionStages history={{ ...base, status }} />);
  const panel = screen.getByRole("region", { name: "执行阶段" });
  expect(within(panel).getByText(title).closest("[data-stage]")).toHaveAttribute("data-stage", kind);
  expect(screen.queryByRole("list", { name: "工具阶段" })).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("updates one card per tool call and separates the same call ID across retry runs", () => {
  const initial = { ...base, status: "running" as const, tool_events: [event(0)] };
  const { rerender } = render(<SessionStages history={initial} />);
  expect(screen.getByText("已开始")).toBeInTheDocument();
  const events = [event(3, { run_id: "run2" }), event(2, { event_type: "failed", payload: { error: { user_message: "读取失败" } } }),
    event(0), event(1, { call_id: "call2", tool_name: "read_url", event_type: "completed" })];
  const snapshot = JSON.stringify(events);
  rerender(<SessionStages history={{ ...initial, tool_events: events }} />);
  expect(within(screen.getByRole("list", { name: "工具阶段" })).getAllByRole("listitem")).toHaveLength(3);
  expect(screen.getByText("读取失败")).toBeInTheDocument();
  expect(screen.getByText("执行记录 2")).toBeInTheDocument();
  expect(JSON.stringify(events)).toBe(snapshot);
});

it("does not expose raw tool outputs or technical errors and bounds user summaries", () => {
  render(<SessionStages history={{ ...base, status: "failed", tool_events: [
    event(0, { event_type: "failed", payload: { arguments: { token: "SECRET" }, error: { message: "STACKTRACE", details: "PRIVATE", user_message: "请检查文件" } } }),
    event(1, { call_id: "other", event_type: "completed", payload: { result: "RAW BOOK CONTENT", summary: "文".repeat(300) } }),
    event(2, { call_id: "third", event_type: "failed", payload: { error: "RAW ERROR" } }),
  ] }} />);
  expect(screen.getByText("请检查文件")).toBeInTheDocument();
  expect(screen.getByText("文".repeat(240) + "…")).toBeInTheDocument();
  expect(screen.getByText("工具执行失败，未记录可展示的错误说明。")).toBeInTheDocument();
  for (const text of ["SECRET", "STACKTRACE", "PRIVATE", "RAW BOOK CONTENT", "RAW ERROR"]) {
    expect(document.body.textContent).not.toContain(text);
  }
});

it("never treats missing tool completion as success or a running tool after the Session stops", () => {
  for (const status of ["cancelled", "failed", "completed", "waiting_input"] as const) {
    expect(toolStages({ ...base, status, tool_events: [event(0)] })[0].state).toBe("unfinished");
  }
  const stages = toolStages({ ...base, status: "running", tool_events: [event(0), event(1, { run_id: "new" })] });
  expect(stages.map((stage) => stage.state)).toEqual(["unfinished", "started"]);
});

it("does not infer overall success from a completed tool", () => {
  render(<SessionStages history={{ ...base, status: "running", tool_events: [event(0, { event_type: "completed" })] }} />);
  expect(screen.getByText("执行中")).toBeInTheDocument();
  expect(screen.queryByText("会话已完成")).not.toBeInTheDocument();
});

it("renders user summaries as text, not executable markup", () => {
  render(<SessionStages history={{ ...base, tool_events: [event(0, { event_type: "completed", payload: { summary: "<img src=x onerror=alert(1)>" } })] }} />);
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
});
