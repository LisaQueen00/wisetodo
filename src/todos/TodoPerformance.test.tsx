// @vitest-environment jsdom
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TodoList } from "./TodoList";
import type { Todo } from "./types";

afterEach(cleanup);

it.each([100, 1000])("renders and toggles %i Todos without losing rows", (count) => {
  const todos: Todo[] = Array.from({ length: count }, (_, index) => ({
    id: `todo-${index}`, topic: `任务 ${index}`, priority: 0, position: index,
    created_at: "2026-09-10T00:00:00Z", updated_at: "2026-09-10T00:00:00Z",
    completed: index % 5 === 0, progress: index % 5 === 0 ? 1 : 0,
    items: Array.from({ length: 10 }, (_, position) => ({
      id: `${index}-${position}`, todo_id: `todo-${index}`, topic: `子项 ${position}`,
      position, completed: index % 5 === 0,
    })),
  }));
  const start = performance.now();
  const view = render(<TodoList todos={todos} actions={{
    mutations: { create: vi.fn(), update: vi.fn(), delete: vi.fn(),
      move: vi.fn(), setItemCompleted: vi.fn() },
    onSaved: vi.fn(), onDeleted: vi.fn(),
  }} />);
  const mountMs = performance.now() - start;
  const cards = Array.from(view.container.querySelectorAll<HTMLElement>("[data-todo-id]"));
  expect(cards).toHaveLength(count);
  expect(cards.map((card) => card.dataset.todoId)).toEqual([
    ...todos.filter((todo) => !todo.completed), ...todos.filter((todo) => todo.completed),
  ].map((todo) => todo.id));
  const target = cards[Math.floor(count / 2)];
  const toggle = target.querySelector<HTMLButtonElement>("button[aria-expanded]")!;
  const toggleStart = performance.now();
  fireEvent.click(toggle);
  const toggleMs = performance.now() - toggleStart;
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(target.querySelectorAll("ol > li")).toHaveLength(10);
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  expect(view.container.querySelectorAll("[data-todo-id]")).toHaveLength(count);
  // Diagnostic samples, not browser frame-time assertions: jsdom has no layout/paint.
  console.info(JSON.stringify({ count, children: count * 10, mountMs, toggleMs,
    domNodes: view.container.querySelectorAll("*").length }));
}, 30_000);
