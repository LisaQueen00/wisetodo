// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { loadPreviewTodos } from "./preview";
import type { Todo, TodoDraft, TodoMutations } from "./types";

afterEach(cleanup);

it("creates, edits child rows, updates the visible list and retries a failed deletion", async () => {
  const [base] = await loadPreviewTodos();
  let stored: Todo = base;
  let nextItem = 0;
  const persist = (draft: TodoDraft) => {
    stored = { ...stored, topic: draft.topic, priority: draft.priority,
      items: draft.items.map((item, position) => ({
        id: item.id ?? `child-${nextItem++}`, todo_id: base.id, topic: item.topic, position, completed: false,
      })) };
    return stored;
  };
  const mutations: TodoMutations = {
    create: vi.fn(async (draft) => persist(draft)),
    update: vi.fn(async (_id, draft) => persist(draft)),
    delete: vi.fn(async () => undefined),
    setItemCompleted: vi.fn(),
    move: vi.fn(),
  };
  render(<App loadTodos={async () => []} mutations={mutations} />);
  fireEvent.click(await screen.findByRole("button", { name: "新增 Todo" }));
  fireEvent.change(screen.getByLabelText("Todo 标题"), { target: { value: "Reading" } });
  fireEvent.change(screen.getByLabelText("子项 1"), { target: { value: "Chapter 1" } });
  fireEvent.change(screen.getByLabelText("子项 2"), { target: { value: "Chapter 2" } });
  fireEvent.click(screen.getByRole("button", { name: "创建 Todo" }));
  await screen.findByRole("heading", { name: "Reading" });
  expect(mutations.create).toHaveBeenCalledOnce();
  expect(screen.queryByRole("form")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "编辑 Reading" }));
  fireEvent.change(screen.getByLabelText("Todo 标题"), { target: { value: "Reading updated" } });
  fireEvent.change(screen.getByLabelText("优先级"), { target: { value: "1" } });
  fireEvent.click(screen.getByRole("button", { name: "添加子项" }));
  fireEvent.change(screen.getByLabelText("子项 3"), { target: { value: "Chapter 3" } });
  fireEvent.click(screen.getByLabelText("删除子项 1"));
  expect(screen.getByLabelText("删除子项 1")).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "完成编辑" }));
  await screen.findByRole("heading", { name: "Reading updated" });
  expect(mutations.update).toHaveBeenCalledWith(base.id, {
    topic: "Reading updated", priority: base.priority,
    items: [{ id: "child-1", topic: "Chapter 2" }, { id: undefined, topic: "Chapter 3" }],
  });
  fireEvent.click(screen.getByRole("button", { name: "Reading updated" }));
  const children = screen.getByRole("list", { name: "Reading updated的子项" });
  expect(within(children).getAllByRole("listitem").map((item) => item.textContent))
    .toEqual(["Chapter 2", "Chapter 3"]);

  vi.mocked(mutations.delete).mockRejectedValueOnce(new Error("offline"));
  fireEvent.click(screen.getByRole("button", { name: "删除 Reading updated" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("删除失败");
  expect(screen.getByRole("heading", { name: "Reading updated" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "删除 Reading updated" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "删除 Reading updated" }));
  expect(await screen.findByText("还没有 Todo")).toBeInTheDocument();
  expect(mutations.delete).toHaveBeenCalledTimes(2);
});
