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

  it("groups every todo by completion while preserving source order and content within each group", async () => {
    const previewTodos = await loadPreviewTodos();
    const todos = [previewTodos[2], previewTodos[1], previewTodos[0], ...previewTodos.slice(3)];
    const sourceSnapshot = JSON.stringify(todos);
    Object.freeze(todos);

    render(<App loadTodos={async () => todos} preview />);
    expect(screen.getByText("正在读取 Todo…")).toBeInTheDocument();
    await screen.findByRole("list", { name: "未完成 Todo" });

    const workspace = within(screen.getByRole("region", { name: "Todo 工作区" }));
    expect(workspace.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent))
      .toEqual(["未完成", "已完成"]);
    expect(screen.getAllByRole("list").map((list) => list.getAttribute("aria-label")))
      .toEqual(["未完成 Todo", "已完成 Todo"]);
    expect(screen.getAllByRole("listitem")).toHaveLength(todos.length);

    for (const completed of [false, true]) {
      const label = completed ? "已完成" : "未完成";
      const expectedTodos = todos.filter((todo) => todo.completed === completed);
      const list = screen.getByRole("list", { name: `${label} Todo` });
      const rows = within(list).getAllByRole("listitem");
      const section = within(screen.getByRole("region", { name: label }));
      expect(section.getByText(String(expectedTodos.length), { exact: true }))
        .toBeInTheDocument();
      expect(rows).toHaveLength(expectedTodos.length);
      rows.forEach((row, index) => {
        const todo = expectedTodos[index];
        expect(within(row).getByRole("heading", { level: 3 })).toHaveTextContent(todo.topic);
        expect(within(row).getByText(todo.priority === 1 ? "高优先级" : "普通")).toBeInTheDocument();
        expect(within(row).getByRole("progressbar")).toHaveAttribute("value", String(todo.progress));
        expect(within(row).getByText(`${Math.round(todo.progress * 100)}% · ${todo.items.length} 个子项`))
          .toBeInTheDocument();
      });
    }

    expect(JSON.stringify(todos)).toBe(sourceSnapshot);
    expect(screen.getByText("示例数据预览 · 不会写入数据库")).toBeInTheDocument();
  });

  it.each([false, true])("only displays the nonempty group when completed is %s", async (completed) => {
    const todos = (await loadPreviewTodos()).filter((todo) => todo.completed === completed);
    const label = completed ? "已完成" : "未完成";
    const hiddenLabel = completed ? "未完成" : "已完成";
    render(<App loadTodos={async () => todos} />);

    const list = await screen.findByRole("list", { name: `${label} Todo` });
    expect(within(list).getAllByRole("listitem")).toHaveLength(todos.length);
    expect(screen.getByRole("heading", { level: 2, name: label })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: hiddenLabel })).not.toBeInTheDocument();
    expect(screen.queryByRole("list", { name: `${hiddenLabel} Todo` })).not.toBeInTheDocument();
    expect(screen.queryByText("还没有 Todo")).not.toBeInTheDocument();
  });

  it("moves a todo between groups after reloading a changed completion state without duplicates", async () => {
    const todos = (await loadPreviewTodos()).slice(0, 3);
    const changedTodo = todos[0];
    const { rerender } = render(<App loadTodos={async () => todos} />);
    const incompleteList = await screen.findByRole("list", { name: "未完成 Todo" });
    expect(within(incompleteList).getByRole("heading", { name: changedTodo.topic })).toBeInTheDocument();

    const completedTodos = todos.map((todo) => todo.id === changedTodo.id ? {
      ...todo,
      items: todo.items.map((item) => ({ ...item, completed: true })),
      completed: true,
      progress: 1,
    } : todo);
    rerender(<App loadTodos={async () => completedTodos} />);

    const completeList = await screen.findByRole("list", { name: "已完成 Todo" });
    expect(within(completeList).getByRole("heading", { name: changedTodo.topic })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "未完成 Todo" }))
      .queryByRole("heading", { name: changedTodo.topic })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: changedTodo.topic })).toHaveLength(1);
    expect(screen.getAllByRole("listitem")).toHaveLength(todos.length);

    rerender(<App loadTodos={async () => todos} />);
    const reloadedIncompleteList = await screen.findByRole("list", { name: "未完成 Todo" });
    expect(within(reloadedIncompleteList).getByRole("heading", { name: changedTodo.topic })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "已完成 Todo" }))
      .queryByRole("heading", { name: changedTodo.topic })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: changedTodo.topic })).toHaveLength(1);
    expect(screen.getAllByRole("listitem")).toHaveLength(todos.length);
  });

  it("shows a real empty result separately from an unconnected data source", async () => {
    render(<App loadTodos={async () => []} />);
    expect(await screen.findByText("还没有 Todo")).toBeInTheDocument();
    expect(screen.queryByText("请通过桌面应用查看 Todo")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "未完成" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "已完成" })).not.toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
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
    await screen.findByRole("list", { name: "未完成 Todo" });
    resolveOld([]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(24));
  });

  it.each(["ready", "error"])("shows loading when switching away from a %s source", async (status) => {
    const oldLoad = status === "ready"
      ? loadPreviewTodos
      : async () => { throw new Error("Database unavailable"); };
    const { rerender } = render(<App loadTodos={oldLoad} />);
    if (status === "ready") {
      await screen.findByRole("list", { name: "未完成 Todo" });
    } else {
      await screen.findByRole("alert");
    }

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
