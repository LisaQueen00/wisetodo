// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { SessionPanel } from "./SessionPanel";
import type { SessionApi, SessionHistory } from "./types";
import type { Todo } from "../todos/types";

afterEach(cleanup);
const first: SessionHistory = { id: "one", label: "First", status: "ready", created_at: "2026-01-01", updated_at: "2026-01-01", messages: [], tool_events: [] };
const todo: Todo = { id: "todo", topic: "新任务", priority: 0, progress: 0, completed: false, position: 0, created_at: "2026-01-01", updated_at: "2026-01-01", items: [
  { id: "a", todo_id: "todo", topic: "一步", position: 0, completed: false },
  { id: "b", todo_id: "todo", topic: "二步", position: 1, completed: false },
] };
function api(): SessionApi {
  return { executesMessages: true, list: vi.fn(async () => [first]), get: vi.fn(async () => first),
    create: vi.fn(), delete: vi.fn(), retry: vi.fn(), send: vi.fn() };
}
async function openAndType() {
  fireEvent.click(await screen.findByRole("button", { name: "First待开始" }));
  await screen.findByRole("heading", { name: "First" });
  fireEvent.change(screen.getByLabelText("聊天输入"), { target: { value: "生成任务" } });
}

it("refreshes the Todo list and locks chat only after committed response", async () => {
  const service = api();
  let committed = false;
  const load = vi.fn(async () => committed ? [todo] : []);
  vi.mocked(service.send).mockImplementation(async () => {
    committed = true;
    return { ...first, status: "completed", messages: [{ id: "reply", session_id: first.id, role: "assistant", content: "已创建：新任务", attachments: [], position: 0, created_at: first.created_at }] };
  });
  render(<App sessionApi={service} loadTodos={load} />);
  await openAndType();
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByText("已创建：新任务");
  expect(await screen.findByText("共 1 个 Todo")).toBeInTheDocument();
  expect(screen.getByLabelText("聊天输入（会话已完成，只读）")).toBeDisabled();
});

it("sends the explicitly selected edit target and keeps clarification editable", async () => {
  const service = api();
  vi.mocked(service.send).mockResolvedValue({ ...first, status: "waiting_input" });
  render(<SessionPanel api={service} loadTodos={async () => [todo]} />);
  await openAndType();
  await screen.findByRole("option", { name: "新任务" });
  fireEvent.change(screen.getByLabelText("编辑目标"), { target: { value: todo.id } });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await waitFor(() => expect(service.send).toHaveBeenCalledWith(first.id, expect.any(String), "生成任务", [], [], todo.id));
  await waitFor(() => expect(screen.getByLabelText("聊天输入")).toBeEnabled());
});

it("recovers saved input after execution failure and retries without resending", async () => {
  const service = api();
  vi.mocked(service.send).mockImplementation(async (_id, messageId, content) => {
    vi.mocked(service.get).mockResolvedValue({ ...first, status: "failed", messages: [
      { id: messageId, session_id: first.id, role: "user", content, attachments: [], position: 0, created_at: first.created_at },
    ] });
    throw "无法保存待办，请重试。";
  });
  vi.mocked(service.retry).mockResolvedValue({ ...first, status: "completed" });
  const committed = vi.fn();
  render(<SessionPanel api={service} onCommitted={committed} />);
  await openAndType();
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByText("无法保存待办，请重试。");
  expect(screen.getByLabelText("聊天输入")).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  await waitFor(() => expect(committed).toHaveBeenCalledOnce());
  expect(service.send).toHaveBeenCalledTimes(1);
});
