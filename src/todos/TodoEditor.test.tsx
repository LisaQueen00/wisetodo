// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TodoEditor } from "./TodoEditor";
import { loadPreviewTodos } from "./preview";
import type { Todo, TodoDraft, TodoMutations } from "./types";

beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.useRealTimers(); });

function savedTodo(todo: Todo, draft: TodoDraft): Todo {
  return { ...todo, topic: draft.topic.trim(), priority: draft.priority,
    items: draft.items.map((item, position) => ({
      id: item.id ?? `saved-${position}`, todo_id: todo.id, topic: item.topic.trim(), completed: false, position,
    })) };
}

async function setup(todo?: Todo) {
  const [base] = await loadPreviewTodos();
  const mutations: TodoMutations = {
    create: vi.fn(async (draft) => savedTodo(base, draft)),
    update: vi.fn(async (_id, draft) => savedTodo(todo ?? base, draft)),
    delete: vi.fn(async () => undefined),
  };
  const onSaved = vi.fn();
  const onClose = vi.fn();
  render(<TodoEditor todo={todo} mutations={mutations} onSaved={onSaved} onClose={onClose} />);
  return { mutations, onSaved, onClose };
}

describe("TodoEditor", () => {
  it("creates only after valid explicit submission and supports adding/removing draft rows", async () => {
    const { mutations, onSaved, onClose } = await setup();
    fireEvent.click(screen.getByRole("button", { name: "创建 Todo" }));
    expect(screen.getByRole("alert")).toHaveTextContent("标题");
    expect(mutations.create).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Todo 标题"), { target: { value: "阅读" } });
    fireEvent.change(screen.getByLabelText("子项 1"), { target: { value: "第一章" } });
    fireEvent.change(screen.getByLabelText("子项 2"), { target: { value: "第二章" } });
    expect(screen.getByLabelText("删除子项 1")).toBeDisabled();
    fireEvent.click(screen.getByText("添加子项"));
    fireEvent.click(screen.getByLabelText("删除子项 3"));
    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(mutations.create).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "创建 Todo" })); });
    expect(mutations.create).toHaveBeenCalledOnce();
    expect(onSaved).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("debounces changes, cancels invalid input and flushes the latest snapshot on finish", async () => {
    const [todo] = await loadPreviewTodos();
    const { mutations, onClose } = await setup(todo);
    const title = screen.getByLabelText("Todo 标题");
    fireEvent.change(title, { target: { value: "Draft" } });
    await act(() => vi.advanceTimersByTimeAsync(399));
    expect(mutations.update).not.toHaveBeenCalled();
    fireEvent.change(title, { target: { value: "   " } });
    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(mutations.update).not.toHaveBeenCalled();
    fireEvent.change(title, { target: { value: "Latest" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "完成编辑" })); });
    expect(mutations.update).toHaveBeenCalledExactlyOnceWith(todo.id, {
      topic: "Latest", priority: todo.priority,
      items: todo.items.map((item) => ({ id: item.id, topic: item.topic })),
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("keeps a failed draft for retry", async () => {
    const [todo] = await loadPreviewTodos();
    const { mutations, onSaved } = await setup(todo);
    vi.mocked(mutations.update).mockRejectedValueOnce(new Error("offline"));
    fireEvent.change(screen.getByLabelText("子项 1"), { target: { value: "Changed" } });
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(screen.getByRole("alert")).toHaveTextContent("保存失败");
    expect(screen.getByLabelText("子项 1")).toHaveValue("Changed");
    expect(onSaved).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByText("重试保存")); });
    expect(mutations.update).toHaveBeenCalledTimes(2);
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it("flushes when focus leaves the form without waiting for the debounce timer", async () => {
    const [todo] = await loadPreviewTodos();
    const { mutations } = await setup(todo);
    const input = screen.getByLabelText("Todo 标题");
    fireEvent.change(input, { target: { value: "Blur save" } });
    await act(async () => { fireEvent.blur(input, { relatedTarget: null }); });
    expect(mutations.update).toHaveBeenCalledOnce();
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(mutations.update).toHaveBeenCalledOnce();
  });

  it("does not autosave an unfinished IME composition", async () => {
    const [todo] = await loadPreviewTodos();
    const { mutations } = await setup(todo);
    const title = screen.getByLabelText("Todo 标题");
    fireEvent.compositionStart(title);
    fireEvent.change(title, { target: { value: "拼音" } });
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(mutations.update).not.toHaveBeenCalled();
    fireEvent.compositionEnd(title);
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(mutations.update).toHaveBeenCalledOnce();
  });

  it("uses newly assigned IDs for a queued edit without overwriting newer input", async () => {
    const [todo] = await loadPreviewTodos();
    const { mutations, onSaved } = await setup(todo);
    let resolve!: (todo: Todo) => void;
    vi.mocked(mutations.update).mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    fireEvent.click(screen.getByText("添加子项"));
    fireEvent.change(screen.getByLabelText("子项 3"), { target: { value: "New" } });
    await act(() => vi.advanceTimersByTimeAsync(400));
    fireEvent.change(screen.getByLabelText("子项 3"), { target: { value: "Newer" } });
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(mutations.update).toHaveBeenCalledTimes(1);
    const firstDraft = vi.mocked(mutations.update).mock.calls[0][1];
    await act(async () => { resolve(savedTodo(todo, firstDraft)); });
    expect(mutations.update).toHaveBeenCalledTimes(2);
    expect(vi.mocked(mutations.update).mock.calls[1][1].items[2]).toEqual({ id: "saved-2", topic: "Newer" });
    expect(screen.getByLabelText("子项 3")).toHaveValue("Newer");
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it("can discard pending edits without a write", async () => {
    const [todo] = await loadPreviewTodos();
    const { mutations, onClose } = await setup(todo);
    fireEvent.change(screen.getByLabelText("Todo 标题"), { target: { value: "Discard" } });
    fireEvent.click(screen.getByText("放弃未保存修改"));
    await act(() => vi.advanceTimersByTimeAsync(400));
    expect(mutations.update).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledOnce();
    expect(within(screen.getByRole("form")).queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
