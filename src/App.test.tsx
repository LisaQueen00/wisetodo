// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { loadPreviewTodos } from "./todos/preview";
import type { Todo } from "./todos/types";

afterEach(cleanup);

describe("App", () => {
  it("renders both primary workspace areas", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "WiseTodo" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument();
    expect(screen.getByText("请通过桌面应用查看 Todo")).toBeInTheDocument();
  });

  it("renders every returned todo in source order with its progress", async () => {
    const todos = await loadPreviewTodos();
    render(<App loadTodos={async () => todos} preview />);
    expect(screen.getByText("正在读取 Todo…")).toBeInTheDocument();
    const list = await screen.findByRole("list", { name: "全部 Todo" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(todos.length);
    rows.forEach((row, index) => {
      expect(within(row).getByRole("heading")).toHaveTextContent(todos[index].topic);
      expect(within(row).getByRole("progressbar")).toHaveAttribute("value", String(todos[index].progress));
    });
    expect(screen.getByText("示例数据预览 · 不会写入数据库")).toBeInTheDocument();
  });

  it("shows a real empty result separately from an unconnected data source", async () => {
    render(<App loadTodos={async () => []} />);
    expect(await screen.findByText("还没有 Todo")).toBeInTheDocument();
    expect(screen.queryByText("请通过桌面应用查看 Todo")).not.toBeInTheDocument();
  });

  it("allows retry after a read failure", async () => {
    const load = vi.fn<() => Promise<Todo[]>>()
      .mockRejectedValueOnce(new Error("Database unavailable"))
      .mockResolvedValueOnce([]);
    render(<App loadTodos={load} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("读取 Todo 失败");
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    expect(await screen.findByText("还没有 Todo")).toBeInTheDocument();
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("ignores a stale read after its source changes", async () => {
    let resolveOld!: (todos: Todo[]) => void;
    const oldLoad = vi.fn(() => new Promise<Todo[]>((resolve) => { resolveOld = resolve; }));
    const { rerender } = render(<App loadTodos={oldLoad} />);
    await waitFor(() => expect(oldLoad).toHaveBeenCalledOnce());
    const todos = await loadPreviewTodos();
    rerender(<App loadTodos={async () => todos} />);
    await screen.findByRole("list");
    resolveOld([]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(24));
  });

  it.each(["ready", "error"])("shows loading when switching away from a %s source", async (status) => {
    const oldLoad = status === "ready"
      ? loadPreviewTodos
      : async () => { throw new Error("Database unavailable"); };
    const { rerender } = render(<App loadTodos={oldLoad} />);
    await screen.findByRole(status === "ready" ? "list" : "alert");

    let resolveNew!: (todos: Todo[]) => void;
    const newLoad = vi.fn(() => new Promise<Todo[]>((resolve) => { resolveNew = resolve; }));
    rerender(<App loadTodos={newLoad} />);
    expect(screen.getByText("正在读取 Todo…")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await waitFor(() => expect(newLoad).toHaveBeenCalledOnce());
    resolveNew([]);
    expect(await screen.findByText("还没有 Todo")).toBeInTheDocument();
  });
});
