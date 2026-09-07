// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TodoList } from "./TodoList";
import type { Todo } from "./types";

afterEach(cleanup);

function makeTodo(id: string, topic = `Todo ${id}`): Todo {
  return {
    id,
    topic,
    priority: 0,
    position: 0,
    created_at: "2026-09-07T00:00:00Z",
    updated_at: "2026-09-07T00:00:00Z",
    items: [
      { id: `${id}-1`, todo_id: id, topic: `First item of ${id}`, completed: false, position: 0 },
      { id: `${id}-2`, todo_id: id, topic: `Second item of ${id}`, completed: false, position: 1 },
    ],
    progress: 0,
    completed: false,
  };
}

function controlledPanel(button: HTMLElement): HTMLElement {
  const panelId = button.getAttribute("aria-controls");
  expect(panelId).toBeTruthy();
  const panel = document.getElementById(panelId ?? "");
  if (!panel) throw new Error(`Missing controlled panel: ${panelId}`);
  return panel;
}

describe("TodoList expansion", () => {
  it("starts collapsed and toggles an accessible child list from the topic button", () => {
    const todo = makeTodo("book", "阅读一本书");
    render(<TodoList todos={[todo]} />);

    const heading = screen.getByRole("heading", { level: 3, name: todo.topic });
    const button = within(heading).getByRole("button", { name: todo.topic, expanded: false });
    expect(button.tagName).toBe("BUTTON");
    expect(button).toHaveAttribute("type", "button");
    const panel = controlledPanel(button);
    expect(panel).not.toBeVisible();
    expect(screen.queryByRole("list", { name: `${todo.topic}的子项` })).not.toBeInTheDocument();

    fireEvent.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(panel).toBeVisible();
    const childList = within(panel).getByRole("list", { name: `${todo.topic}的子项` });
    expect(childList.tagName).toBe("OL");
    expect(within(childList).getAllByRole("listitem").map((item) => item.textContent))
      .toEqual(todo.items.map((item) => item.topic));

    fireEvent.click(button);

    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(controlledPanel(button)).not.toBeVisible();
    expect(screen.queryByRole("list", { name: `${todo.topic}的子项` })).not.toBeInTheDocument();
  });

  it("renders duplicate child topics in source order without editing data or toggling on child clicks", () => {
    const todo = makeTodo("project");
    todo.items = [
      { ...todo.items[0], topic: "Run tests", completed: true },
      { ...todo.items[1], topic: "Read the implementation" },
      { ...todo.items[1], id: "project-3", topic: "Run tests", position: 2 },
    ];
    todo.progress = 1 / 3;
    const todos = [todo];
    const snapshot = JSON.stringify(todos);
    for (const item of todo.items) Object.freeze(item);
    Object.freeze(todo.items);
    Object.freeze(todo);
    Object.freeze(todos);
    render(<TodoList todos={todos} />);
    const button = screen.getByRole("button", { name: todo.topic });

    fireEvent.click(button);

    const list = screen.getByRole("list", { name: `${todo.topic}的子项` });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((item) => item.textContent))
      .toEqual(["Run tests", "Read the implementation", "Run tests"]);
    expect(within(list).queryByRole("checkbox")).not.toBeInTheDocument();
    expect(within(list).queryByRole("button")).not.toBeInTheDocument();
    fireEvent.click(within(items[1]).getByText("Read the implementation"));
    expect(button).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(button);
    fireEvent.click(button);
    expect(JSON.stringify(todos)).toBe(snapshot);
  });

  it("expands todos independently even when their topics are identical", () => {
    const todos = [makeTodo("first", "重复标题"), makeTodo("second", "重复标题")];
    render(<TodoList todos={todos} />);
    const [firstButton, secondButton] = screen.getAllByRole("button", { name: "重复标题" });
    const firstPanel = controlledPanel(firstButton);
    const secondPanel = controlledPanel(secondButton);
    expect(firstPanel.id).not.toBe(secondPanel.id);

    fireEvent.click(firstButton);
    expect(firstPanel).toBeVisible();
    expect(secondPanel).not.toBeVisible();
    expect(secondButton).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(secondButton);
    expect(firstPanel).toBeVisible();
    expect(secondPanel).toBeVisible();
    expect(within(firstPanel).getByText(todos[0].items[0].topic)).toBeInTheDocument();
    expect(within(secondPanel).getByText(todos[1].items[0].topic)).toBeInTheDocument();

    fireEvent.click(firstButton);
    expect(firstPanel).not.toBeVisible();
    expect(secondPanel).toBeVisible();
    expect(secondButton).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps expansion by ID through renaming, reordering, and moving between completion groups", () => {
    const first = makeTodo("first");
    const second = makeTodo("second");
    const third = makeTodo("third");
    const { rerender } = render(<TodoList todos={[first, second, third]} />);
    fireEvent.click(screen.getByRole("button", { name: first.topic }));
    fireEvent.click(screen.getByRole("button", { name: second.topic }));

    const renamed = { ...first, topic: "Renamed first Todo" };
    rerender(<TodoList todos={[third, renamed, second]} />);
    expect(screen.getByRole("button", { name: renamed.topic })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: second.topic })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: third.topic })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("list", { name: `${renamed.topic}的子项` })).toBeVisible();
    expect(screen.queryByRole("button", { name: first.topic })).not.toBeInTheDocument();

    const completed = {
      ...renamed,
      completed: true,
      progress: 1,
      items: renamed.items.map((item) => ({ ...item, completed: true })),
    };
    rerender(<TodoList todos={[third, second, completed]} />);
    const completedSection = within(screen.getByRole("region", { name: "已完成" }));
    const movedButton = completedSection.getByRole("button", { name: completed.topic, expanded: true });
    expect(controlledPanel(movedButton)).toBeVisible();
    expect(screen.getByRole("button", { name: second.topic })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: third.topic })).toHaveAttribute("aria-expanded", "false");

    rerender(<TodoList todos={[renamed, second, third]} />);
    const incompleteSection = within(screen.getByRole("region", { name: "未完成" }));
    const returnedButton = incompleteSection.getByRole("button", { name: renamed.topic, expanded: true });
    expect(controlledPanel(returnedButton)).toBeVisible();
    expect(screen.getAllByRole("button", { name: renamed.topic })).toHaveLength(1);
  });

  it("does not transfer expansion to a replacement Todo with a new ID and the same topic", () => {
    const todo = makeTodo("original", "Read a book");
    const { rerender } = render(<TodoList todos={[todo]} />);
    fireEvent.click(screen.getByRole("button", { name: todo.topic }));

    const replacement = makeTodo("replacement", todo.topic);
    rerender(<TodoList todos={[replacement]} />);

    const button = screen.getByRole("button", { name: replacement.topic, expanded: false });
    expect(controlledPanel(button)).not.toBeVisible();
    expect(screen.queryByText(todo.items[0].topic)).not.toBeInTheDocument();
  });

  it("starts collapsed again after the list is unmounted", () => {
    const todo = makeTodo("book");
    const { unmount } = render(<TodoList todos={[todo]} />);
    fireEvent.click(screen.getByRole("button", { name: todo.topic }));
    expect(screen.getByRole("list", { name: `${todo.topic}的子项` })).toBeVisible();

    unmount();
    render(<TodoList todos={[todo]} />);

    const button = screen.getByRole("button", { name: todo.topic, expanded: false });
    expect(controlledPanel(button)).not.toBeVisible();
  });
});
