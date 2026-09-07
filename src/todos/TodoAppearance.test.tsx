// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TodoList } from "./TodoList";
import { loadPreviewTodos } from "./preview";
import type { Todo, TodoActions } from "./types";

afterEach(cleanup);

it.each([0, 1] as const)("keeps priority %i identifiable on both active and completed cards", async (priority) => {
  const [base] = await loadPreviewTodos();
  const active: Todo = { ...base, priority };
  const done: Todo = { ...active, id: "done", topic: "Completed task", completed: true, progress: 1,
    items: active.items.map((item) => ({ ...item, completed: true })) };
  render(<TodoList todos={[active, done]} />);
  for (const todo of [active, done]) {
    const card = screen.getByRole("button", { name: todo.topic }).closest("li")!;
    expect(card).toHaveClass("todo-card");
    expect(card).toHaveAttribute("data-priority", String(priority));
    expect(card).toHaveAttribute("data-completed", String(todo.completed));
    expect(within(card).getByText(priority === 1 ? "高优先级" : "普通")).toHaveClass("todo-priority");
    expect(within(card).queryByText("已完成") !== null).toBe(todo.completed);
  }
});

it("only strikes completed child text and removes completion styling when reopened", async () => {
  const [base] = await loadPreviewTodos();
  const partial: Todo = { ...base, progress: 0.5,
    items: base.items.map((item, index) => ({ ...item, completed: index === 0 })) };
  const { rerender } = render(<TodoList todos={[partial]} />);
  fireEvent.click(screen.getByRole("button", { name: partial.topic }));
  expect(screen.getByText(partial.items[0].topic)).toHaveClass("line-through");
  expect(screen.getByText(partial.items[1].topic)).not.toHaveClass("line-through");
  rerender(<TodoList todos={[base]} />);
  expect(screen.getByText(base.items[0].topic)).not.toHaveClass("line-through");
  expect(screen.getByRole("button", { name: base.topic }).closest("li")).toHaveAttribute("data-completed", "false");
});

it("keeps completed tasks editable with an undimmed editor", async () => {
  const todos = await loadPreviewTodos();
  const done = todos[2];
  const actions: TodoActions = {
    mutations: { create: vi.fn(), update: vi.fn(), delete: vi.fn(), move: vi.fn(), setItemCompleted: vi.fn() },
    onSaved: vi.fn(), onDeleted: vi.fn(),
  };
  render(<TodoList todos={[done]} actions={actions} />);
  expect(screen.getByRole("button", { name: `编辑 ${done.topic}` })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: `编辑 ${done.topic}` }));
  expect(screen.getByRole("form").closest("li")).toHaveAttribute("data-editing", "true");
  expect(screen.getByLabelText("Todo 标题")).toBeEnabled();
});
