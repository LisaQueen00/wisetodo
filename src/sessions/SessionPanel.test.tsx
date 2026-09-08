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
  return { list: vi.fn(async () => [first, second]), get: vi.fn(async (id) => id === first.id ? first : second),
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
