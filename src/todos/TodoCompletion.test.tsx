// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { loadPreviewTodos } from "./preview";
import type { Todo, TodoMutations } from "./types";

afterEach(cleanup);

async function setup() {
  const [original] = await loadPreviewTodos();
  let stored = original;
  const mutations: TodoMutations = {
    move: vi.fn(),
    create: vi.fn(), update: vi.fn(), delete: vi.fn(),
    setItemCompleted: vi.fn(async (_todoId, itemId, completed) => {
      const items = stored.items.map((item) => item.id === itemId ? { ...item, completed } : item);
      stored = { ...stored, items, progress: items.filter((item) => item.completed).length / items.length,
        completed: items.every((item) => item.completed) };
      return stored;
    }),
  };
  render(<App loadTodos={async () => [original]} mutations={mutations} />);
  fireEvent.click(await screen.findByRole("button", { name: original.topic }));
  return { original, mutations };
}

it("saves each child, updates progress and moves completed Todos without collapsing them", async () => {
  const { original, mutations } = await setup();
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  await waitFor(() => expect(screen.getAllByRole("checkbox")[0]).toBeChecked());
  expect(mutations.setItemCompleted).toHaveBeenLastCalledWith(original.id, original.items[0].id, true);
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0.5");
  fireEvent.click(screen.getAllByRole("checkbox")[1]);
  await screen.findByRole("list", { name: "已完成 Todo" });
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "1");
  expect(screen.getByRole("button", { name: original.topic })).toHaveAttribute("aria-expanded", "true");
  expect(within(screen.getByRole("list", { name: "已完成 Todo" })).getAllByRole("checkbox")).toHaveLength(2);
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  await screen.findByRole("list", { name: "未完成 Todo" });
  expect(screen.getAllByRole("checkbox")[0]).not.toBeChecked();
  expect(mutations.setItemCompleted).toHaveBeenLastCalledWith(original.id, original.items[0].id, false);
});

it("locks the card during saving and preserves the original state on failure for retry", async () => {
  const { original, mutations } = await setup();
  let reject!: (error: Error) => void;
  vi.mocked(mutations.setItemCompleted).mockReturnValueOnce(new Promise<Todo>((_resolve, fail) => { reject = fail; }));
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  for (const checkbox of screen.getAllByRole("checkbox")) expect(checkbox).toBeDisabled();
  expect(screen.getByRole("button", { name: `编辑 ${original.topic}` })).toBeDisabled();
  expect(screen.getByRole("button", { name: `删除 ${original.topic}` })).toBeDisabled();
  await act(async () => { reject(new Error("offline")); });
  expect(screen.getByRole("alert")).toHaveTextContent("完成状态保存失败");
  expect(screen.getAllByRole("checkbox")[0]).not.toBeChecked();
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  await waitFor(() => expect(screen.getAllByRole("checkbox")[0]).toBeChecked());
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
