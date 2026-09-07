import { invoke } from "@tauri-apps/api/core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { desktopMutations, loadDesktopTodos } from "./desktop";
import { loadPreviewTodos } from "./preview";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

beforeEach(() => vi.resetAllMocks());

describe("loadDesktopTodos", () => {
  it("uses the fixed move command and rejects invalid sorted lists", async () => {
    const todos = await loadPreviewTodos();
    vi.mocked(invoke).mockResolvedValue({ todos });
    expect(await desktopMutations.move("source", "target")).toEqual(todos);
    expect(invoke).toHaveBeenLastCalledWith("todos_move", { todoId: "source", targetId: "target" });
    vi.mocked(invoke).mockResolvedValue({ todos: [{}] });
    await expect(desktopMutations.move("source", "target")).rejects.toThrow();
  });
  it("sends exact child IDs and validates completion responses", async () => {
    const [todo] = await loadPreviewTodos();
    vi.mocked(invoke).mockResolvedValue({ todo });
    expect(await desktopMutations.setItemCompleted(todo.id, todo.items[0].id, true)).toEqual(todo);
    expect(invoke).toHaveBeenLastCalledWith("todos_set_item_completed", {
      todoId: todo.id, itemId: todo.items[0].id, completed: true,
    });
    vi.mocked(invoke).mockResolvedValue({ todo: {} });
    await expect(desktopMutations.setItemCompleted(todo.id, todo.items[0].id, false)).rejects.toThrow();
  });
  it("uses fixed user mutation commands and sends IDs only on updates", async () => {
    const [todo] = await loadPreviewTodos();
    const draft = { topic: todo.topic, priority: todo.priority,
      items: todo.items.map((item) => ({ id: item.id, topic: item.topic })) };
    vi.mocked(invoke).mockResolvedValue({ todo });
    await desktopMutations.create(draft);
    expect(invoke).toHaveBeenLastCalledWith("todos_create", {
      todo: { ...draft, items: draft.items.map((item) => item.topic) },
    });
    await desktopMutations.update(todo.id, draft);
    expect(invoke).toHaveBeenLastCalledWith("todos_update", { todoId: todo.id, todo: draft });
    vi.mocked(invoke).mockResolvedValue({ deleted: true });
    await desktopMutations.delete(todo.id);
    expect(invoke).toHaveBeenLastCalledWith("todos_delete", { todoId: todo.id });
  });
  it("loads the full service response using only the fixed desktop command", async () => {
    const todos = await loadPreviewTodos();
    vi.mocked(invoke).mockResolvedValue({ todos });

    expect(await loadDesktopTodos()).toEqual(todos);
    expect(invoke).toHaveBeenCalledExactlyOnceWith("todos_list");
  });

  it("accepts an explicitly empty database", async () => {
    vi.mocked(invoke).mockResolvedValue({ todos: [] });
    expect(await loadDesktopTodos()).toEqual([]);
  });

  it.each([null, {}, [], { todos: null }, { todos: {} }, { todos: [{}] }])(
    "rejects malformed response %j rather than showing an empty database",
    async (response) => {
      vi.mocked(invoke).mockResolvedValue(response);
      await expect(loadDesktopTodos()).rejects.toThrow("Invalid todos_list response");
    },
  );

  it.each([
    { priority: 2 },
    { progress: "0.5" },
    { progress: Number.NaN },
    { progress: 2 },
    { position: -1 },
    { completed: "false" },
    { created_at: null },
    { items: [] },
    { items: [null, null] },
  ])("rejects invalid todo fields %j", async (fields) => {
    const [todo] = await loadPreviewTodos();
    vi.mocked(invoke).mockResolvedValue({ todos: [{ ...todo, ...fields }] });
    await expect(loadDesktopTodos()).rejects.toThrow("Invalid todos_list response");
  });

  it("rejects a malformed child item", async () => {
    const [todo] = await loadPreviewTodos();
    todo.items[0] = { ...todo.items[0], completed: "false" } as unknown as typeof todo.items[0];
    vi.mocked(invoke).mockResolvedValue({ todos: [todo] });
    await expect(loadDesktopTodos()).rejects.toThrow("Invalid todos_list response");
  });

  it("propagates desktop failures for the workspace retry state", async () => {
    const error = { code: "DATABASE_ERROR", message: "Database unavailable" };
    vi.mocked(invoke).mockRejectedValue(error);
    await expect(loadDesktopTodos()).rejects.toBe(error);
  });
});
