import { invoke } from "@tauri-apps/api/core";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { loadDesktopTodos } from "./desktop";
import { loadPreviewTodos } from "./preview";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

beforeEach(() => vi.resetAllMocks());

describe("loadDesktopTodos", () => {
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
