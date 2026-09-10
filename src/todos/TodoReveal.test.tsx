// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TodoList } from "./TodoList";
import type { Todo } from "./types";

const todo: Todo = {
  id: "one", topic: "读书", priority: 0, position: 0, completed: false, progress: 0,
  created_at: "now", updated_at: "now",
  items: ["甲", "乙"].map((topic, position) => ({ id: topic, todo_id: "one", topic, position, completed: false })),
};
afterEach(() => { cleanup(); vi.useRealTimers(); });
it("does not flash initial history; reveals a write for ten seconds across unchanged refreshes", () => {
  vi.useFakeTimers();
  const view = render(<TodoList todos={[todo]} />);
  expect(view.container.querySelector("[data-reveal]")).toBeNull();
  const changed = { ...todo, topic: "阅读小说" };
  view.rerender(<TodoList todos={[changed]} />);
  act(() => vi.advanceTimersByTime(0));
  expect(screen.getByRole("button", { name: "阅读小说" })).toHaveAttribute("aria-expanded", "true");
  expect(view.container.querySelector("[data-reveal=true]")).not.toBeNull();
  act(() => vi.advanceTimersByTime(5000));
  view.rerender(<TodoList todos={[{ ...changed }]} />);
  expect(view.container.querySelector("[data-reveal=true]")).not.toBeNull();
  act(() => vi.advanceTimersByTime(5000));
  expect(view.container.querySelector("[data-reveal]")).toBeNull();
});
it("reveals the first newly created Todo and clears timers on unmount", () => {
  vi.useFakeTimers();
  const view = render(<TodoList todos={[]} />);
  view.rerender(<TodoList todos={[todo]} />);
  act(() => vi.advanceTimersByTime(0));
  expect(screen.getByRole("button", { name: "读书" })).toHaveAttribute("aria-expanded", "true");
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});
