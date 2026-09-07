// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { loadPreviewTodos } from "./preview";
import type { Todo, TodoMutations } from "./types";

afterEach(cleanup);

async function setup() {
  const [base] = await loadPreviewTodos();
  let stored: Todo[] = ["A", "B", "C"].map((topic, position) => ({ ...base, id: topic, topic, position }));
  const mutations: TodoMutations = {
    create: vi.fn(), update: vi.fn(), delete: vi.fn(), setItemCompleted: vi.fn(),
    move: vi.fn(async (id, targetId) => {
      const next = [...stored];
      const targetIndex = next.findIndex((todo) => todo.id === targetId);
      const [source] = next.splice(next.findIndex((todo) => todo.id === id), 1);
      next.splice(targetIndex, 0, source);
      stored = next.map((todo, position) => ({ ...todo, position }));
      return stored;
    }),
  };
  render(<App loadTodos={async () => stored} mutations={mutations} />);
  await screen.findByRole("button", { name: "A" });
  return mutations;
}

function order() {
  return within(screen.getByRole("list", { name: "未完成 Todo" })).getAllByRole("heading")
    .map((heading) => heading.textContent);
}

it("moves in both directions, disables boundary buttons and preserves expansion", async () => {
  const mutations = await setup();
  expect(screen.getByRole("button", { name: "上移 A" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "下移 C" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "B" }));
  fireEvent.click(screen.getByRole("button", { name: "上移 B" }));
  await waitFor(() => expect(order()).toEqual(["B", "A", "C"]));
  expect(mutations.move).toHaveBeenLastCalledWith("B", "A");
  expect(screen.getByRole("button", { name: "B" })).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(screen.getByRole("button", { name: "下移 B" }));
  await waitFor(() => expect(order()).toEqual(["A", "B", "C"]));
});

it("supports internal drag and drop but ignores external text drops", async () => {
  const mutations = await setup();
  const target = screen.getByRole("button", { name: "A" }).closest("li")!;
  const dataTransfer = { setData: vi.fn(), effectAllowed: "", dropEffect: "" };
  fireEvent.drop(target, { dataTransfer });
  expect(mutations.move).not.toHaveBeenCalled();
  fireEvent.dragStart(screen.getByRole("button", { name: "拖动排序 C" }), { dataTransfer });
  fireEvent.dragOver(target, { dataTransfer });
  expect(dataTransfer.dropEffect).toBe("move");
  fireEvent.drop(target, { dataTransfer });
  await waitFor(() => expect(order()).toEqual(["C", "A", "B"]));
});

it("locks writes while sorting, keeps the old order on failure and allows retry", async () => {
  const mutations = await setup();
  let reject!: (error: Error) => void;
  vi.mocked(mutations.move).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  fireEvent.click(screen.getByRole("button", { name: "下移 A" }));
  expect(screen.getByRole("button", { name: "上移 B" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "编辑 B" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "新增 Todo" })).toBeDisabled();
  await act(async () => { reject(new Error("offline")); });
  expect(screen.getByRole("alert")).toHaveTextContent("排序保存失败");
  expect(order()).toEqual(["A", "B", "C"]);
  fireEvent.click(screen.getByRole("button", { name: "下移 A" }));
  await waitFor(() => expect(order()).toEqual(["B", "A", "C"]));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("rejects cross-priority and cross-completion drops and disables sorting during editing", async () => {
  const samples = await loadPreviewTodos();
  const todos = samples.slice(0, 3);
  const move = vi.fn();
  const mutations: TodoMutations = {
    move, create: vi.fn(), update: vi.fn(), delete: vi.fn(), setItemCompleted: vi.fn(),
  };
  render(<App loadTodos={async () => todos} mutations={mutations} />);
  const handle = await screen.findByRole("button", { name: `拖动排序 ${todos[0].topic}` });
  const dataTransfer = { setData: vi.fn(), effectAllowed: "", dropEffect: "" };
  for (const target of todos.slice(1)) {
    fireEvent.dragStart(handle, { dataTransfer });
    fireEvent.drop(screen.getByRole("button", { name: target.topic }).closest("li")!, { dataTransfer });
    fireEvent.dragEnd(handle, { dataTransfer });
  }
  expect(move).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: `下移 ${todos[0].topic}` })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: `编辑 ${todos[0].topic}` }));
  expect(screen.getByRole("button", { name: `拖动排序 ${todos[1].topic}` })).toBeDisabled();
});

it("disables sorting until an existing completion write has finished", async () => {
  const mutations = await setup();
  let reject!: (error: Error) => void;
  vi.mocked(mutations.setItemCompleted).mockReturnValueOnce(new Promise((_resolve, fail) => { reject = fail; }));
  fireEvent.click(screen.getByRole("button", { name: "A" }));
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  expect(screen.getByRole("button", { name: "上移 B" })).toBeDisabled();
  await act(async () => { reject(new Error("offline")); });
  expect(screen.getByRole("button", { name: "上移 B" })).toBeEnabled();
});
