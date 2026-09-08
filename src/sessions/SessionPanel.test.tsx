// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SessionPanel } from "./SessionPanel";
import type { SessionApi, SessionHistory } from "./types";

afterEach(cleanup);
const first: SessionHistory = { id: "one", label: "First", status: "ready", created_at: "2026-01-01", updated_at: "2026-01-01", messages: [], tool_events: [] };
const second = { ...first, id: "two", label: "Second" };
function api(): SessionApi {
  return { send: vi.fn(), retry: vi.fn(), list: vi.fn(async () => [first, second]), get: vi.fn(async (id) => id === first.id ? first : second),
    create: vi.fn(async (label) => ({ ...first, id: "new", label })), delete: vi.fn(async () => true) };
}

it("loads summaries without automatically opening history, then opens only when selected", async () => {
  const service = api();
  render(<SessionPanel api={service} />);
  const button = await screen.findByRole("button", { name: "First待开始" });
  expect(service.get).not.toHaveBeenCalled();
  expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  fireEvent.click(button);
  await screen.findByRole("heading", { name: "First" });
  expect(service.get).toHaveBeenCalledExactlyOnceWith("one");
  expect(screen.getByText("已加载 0 条消息、0 条工具事件。")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "执行阶段" })).toBeInTheDocument();
  expect(screen.getByText("等待开始")).toBeInTheDocument();
});

it("creates and selects a Session; failed deletion keeps it and retry clears the selection", async () => {
  const service = api();
  render(<SessionPanel api={service} />);
  await screen.findByRole("button", { name: "First待开始" });
  fireEvent.change(screen.getByLabelText("会话标签"), { target: { value: "New" } });
  fireEvent.click(screen.getByRole("button", { name: "新建会话" }));
  await screen.findByRole("heading", { name: "New" });
  expect(service.create).toHaveBeenCalledExactlyOnceWith("New");
  vi.mocked(service.delete).mockRejectedValueOnce(new Error("offline"));
  fireEvent.click(screen.getByLabelText("删除会话 New"));
  await screen.findByRole("alert");
  expect(screen.getByRole("heading", { name: "New" })).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("删除会话 New"));
  await waitFor(() => expect(screen.queryByRole("heading")).not.toBeInTheDocument());
  expect(screen.getByRole("button", { name: "First待开始" })).toBeInTheDocument();
});

it("ignores a late detail response when the user selects another Session", async () => {
  const service = api();
  let resolve!: (value: SessionHistory) => void;
  vi.mocked(service.get).mockReturnValueOnce(new Promise((done) => { resolve = done; }));
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: "First待开始" }));
  fireEvent.click(screen.getByRole("button", { name: "Second待开始" }));
  await screen.findByRole("heading", { name: "Second" });
  await act(async () => { resolve(first); });
  expect(screen.getByRole("heading", { name: "Second" })).toBeInTheDocument();
});

it("retries failed list reads and does not delete running Sessions", async () => {
  const service = api();
  vi.mocked(service.list).mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce([{ ...first, status: "running" }]);
  render(<SessionPanel api={service} />);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "刷新历史" }));
  await screen.findByRole("button", { name: "First执行中" });
  expect(screen.getByLabelText("删除会话 First")).toBeDisabled();
  expect(service.delete).not.toHaveBeenCalled();
});

it("marks completed history read-only while allowing deletion and a new independent Session", async () => {
  const service = api();
  const completed: SessionHistory = { ...first, status: "completed" };
  vi.mocked(service.list).mockResolvedValue([completed]);
  vi.mocked(service.get).mockResolvedValue(completed);
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: "First已完成" }));
  await screen.findByRole("heading", { name: "First" });
  expect(screen.getByText("此会话已完成，只读；如需继续，请新建会话。")).toBeInTheDocument();
  const input = screen.getByRole("textbox", { name: "聊天输入（会话已完成，只读）" });
  expect(input).toBeDisabled();
  expect(input).toHaveAttribute("readonly");
  expect(screen.getByRole("button", { name: "删除会话 First" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "发送" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "新建会话" }));
  await screen.findByRole("heading", { name: "新会话" });
  expect(screen.queryByText("此会话已完成，只读；如需继续，请新建会话。")).not.toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "聊天输入" })).not.toHaveAttribute("readonly");
  expect(screen.getByRole("button", { name: "First已完成" })).toBeInTheDocument();
});

it.each(["failed", "cancelled"] as const)("retries %s history, preserves it on errors and prevents duplicate clicks", async (status) => {
  const service = api();
  const stopped = { ...first, status };
  vi.mocked(service.list).mockResolvedValue([stopped]);
  vi.mocked(service.get).mockResolvedValue(stopped);
  let reject!: (reason: string) => void;
  vi.mocked(service.retry).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }))
    .mockResolvedValueOnce({ ...first, status: "waiting_input" });
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: status === "failed" ? "First失败" : "First已停止" }));
  fireEvent.click(await screen.findByRole("button", { name: "重试" }));
  expect(screen.getByRole("button", { name: "重试" })).toBeDisabled();
  await act(async () => { reject("执行器尚未接入，原状态已保留。"); });
  expect(screen.getByRole("alert")).toHaveTextContent("执行器尚未接入");
  expect(screen.getByRole("heading", { name: "First" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  await screen.findByText("状态：等待补充");
  expect(service.retry).toHaveBeenCalledWith("one");
  expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
});

it("saves multiline input, handles IME, keeps failed drafts and reuses the message ID on retry", async () => {
  const service = api();
  vi.mocked(service.send).mockRejectedValueOnce(new Error("offline"))
    .mockImplementationOnce(async (id, messageId, content) => ({ ...first, messages: [
      { id: messageId, session_id: id, position: 0, role: "user", content, attachments: [], created_at: "date" },
    ] }));
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: "First待开始" }));
  await screen.findByRole("heading", { name: "First" });
  const input = screen.getByRole("textbox", { name: "聊天输入" });
  expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  fireEvent.change(input, { target: { value: "第一行\n第二行" } });
  fireEvent.compositionStart(input);
  fireEvent.keyDown(input, { key: "Enter" });
  expect(service.send).not.toHaveBeenCalled();
  fireEvent.compositionEnd(input);
  fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
  expect(service.send).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByRole("alert");
  expect(input).toHaveValue("第一行\n第二行");
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByRole("list", { name: "聊天消息" });
  expect(vi.mocked(service.send).mock.calls[0]).toEqual(vi.mocked(service.send).mock.calls[1]);
  expect(input).toHaveValue("");
  expect(screen.getByText("消息已保存。执行器尚未接入，暂不会生成回复或 Todo。")).toBeInTheDocument();
});

it("keeps drafts separate across Session switches", async () => {
  const service = api();
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: "First待开始" }));
  await screen.findByRole("heading", { name: "First" });
  fireEvent.change(screen.getByRole("textbox", { name: "聊天输入" }), { target: { value: "First draft" } });
  fireEvent.click(screen.getByRole("button", { name: "Second待开始" }));
  await screen.findByRole("heading", { name: "Second" });
  expect(screen.getByRole("textbox", { name: "聊天输入" })).toHaveValue("");
  fireEvent.click(screen.getByRole("button", { name: "First待开始" }));
  await screen.findByRole("heading", { name: "First" });
  expect(screen.getByRole("textbox", { name: "聊天输入" })).toHaveValue("First draft");
});

it("adds and removes URL attachments, preserves them on failure and sends without text", async () => {
  const service = api();
  vi.mocked(service.send).mockRejectedValueOnce(new Error("offline"))
    .mockImplementationOnce(async (id, messageId, content, urls) => ({ ...first, messages: [{
      id: messageId, session_id: id, position: 0, role: "user", content, attachments: urls ?? [], created_at: "date",
    }] }));
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: "First待开始" }));
  await screen.findByRole("heading", { name: "First" });
  const urlInput = screen.getByLabelText("URL 附件");
  fireEvent.change(urlInput, { target: { value: "https://example.com" } });
  fireEvent.click(screen.getByRole("button", { name: "添加链接" }));
  expect(screen.getByRole("button", { name: "发送" })).toBeEnabled();
  fireEvent.click(screen.getByLabelText("移除链接 https://example.com"));
  expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  fireEvent.change(urlInput, { target: { value: "https://example.org" } });
  fireEvent.keyDown(urlInput, { key: "Enter" });
  expect(service.send).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("移除链接 https://example.org")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByText("附件：https://example.org");
  expect(vi.mocked(service.send).mock.calls[0]).toEqual(vi.mocked(service.send).mock.calls[1]);
  expect(vi.mocked(service.send).mock.calls[1][2]).toBe("");
  expect(vi.mocked(service.send).mock.calls[1][3]).toEqual(["https://example.org"]);
  expect(screen.queryByRole("list", { name: "待发送链接" })).not.toBeInTheDocument();
});

it("accepts file drops, removes references and persists a file-only message", async () => {
  const service = api();
  let drop!: (paths: string[], x: number, y: number) => void;
  service.listenFileDrops = vi.fn(async (handler) => { drop = handler; return vi.fn(); });
  vi.mocked(service.send).mockImplementation(async (id, messageId, content, urls, files) => ({ ...first, messages: [{
    id: messageId, session_id: id, position: 0, role: "user", content, attachments: [...(urls ?? []), ...(files ?? [])], created_at: "date",
  }] }));
  render(<SessionPanel api={service} />);
  fireEvent.click(await screen.findByRole("button", { name: "First待开始" }));
  await screen.findByRole("heading", { name: "First" });
  const input = screen.getByRole("textbox", { name: "聊天输入" });
  vi.spyOn(input, "getBoundingClientRect").mockReturnValue({ left: 0, top: 0, right: 100, bottom: 100 } as DOMRect);
  await act(async () => { drop(["D:/book.pdf", "D:/book.pdf"], 20, 20); });
  expect(screen.getAllByLabelText("移除文件 D:/book.pdf")).toHaveLength(1);
  fireEvent.click(screen.getByLabelText("移除文件 D:/book.pdf"));
  expect(screen.getByRole("button", { name: "发送" })).toBeDisabled();
  await act(async () => { drop(["D:/book.pdf"], 20, 20); });
  fireEvent.click(screen.getByRole("button", { name: "发送" }));
  await screen.findByText("附件：D:/book.pdf");
  expect(vi.mocked(service.send).mock.calls[0][4]).toEqual(["D:/book.pdf"]);
  expect(screen.queryByRole("list", { name: "待发送文件" })).not.toBeInTheDocument();
});
