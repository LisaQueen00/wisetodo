import { invoke } from "@tauri-apps/api/core";
import type { LoadTodos, Todo, TodoItem, TodoMutations } from "./types";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPosition(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function isTodoItem(value: unknown): value is TodoItem {
  return isObject(value)
    && typeof value.id === "string"
    && typeof value.todo_id === "string"
    && typeof value.topic === "string"
    && typeof value.completed === "boolean"
    && isPosition(value.position);
}

function isTodo(value: unknown): value is Todo {
  return isObject(value)
    && typeof value.id === "string"
    && typeof value.topic === "string"
    && (value.priority === 0 || value.priority === 1)
    && isPosition(value.position)
    && typeof value.created_at === "string"
    && typeof value.updated_at === "string"
    && Array.isArray(value.items)
    && value.items.length >= 2
    && value.items.every(isTodoItem)
    && typeof value.progress === "number"
    && Number.isFinite(value.progress)
    && value.progress >= 0
    && value.progress <= 1
    && typeof value.completed === "boolean";
}

export const loadDesktopTodos: LoadTodos = async () => {
  // The desktop command owns the database path and the IPC method.
  const result = await invoke<unknown>("todos_list");
  if (!isObject(result) || !Array.isArray(result.todos) || !result.todos.every(isTodo)) {
    throw new Error("Invalid todos_list response");
  }
  return result.todos;
};

function savedTodo(result: unknown): Todo {
  if (!isObject(result) || !isTodo(result.todo)) throw new Error("Invalid saved Todo response");
  return result.todo;
}

export const desktopMutations: TodoMutations = {
  async move(todoId, targetId) {
    const result = await invoke<unknown>("todos_move", { todoId, targetId });
    if (!isObject(result) || !Array.isArray(result.todos) || !result.todos.every(isTodo)) {
      throw new Error("Invalid todos_move response");
    }
    return result.todos;
  },
  async setItemCompleted(todoId, itemId, completed) {
    return savedTodo(await invoke("todos_set_item_completed", { todoId, itemId, completed }));
  },
  async create(draft) {
    return savedTodo(await invoke("todos_create", {
      todo: { ...draft, items: draft.items.map((item) => item.topic) },
    }));
  },
  async update(todoId, draft) {
    return savedTodo(await invoke("todos_update", { todoId, todo: draft }));
  },
  async delete(todoId) {
    const result = await invoke<unknown>("todos_delete", { todoId });
    if (!isObject(result) || typeof result.deleted !== "boolean") {
      throw new Error("Invalid delete response");
    }
  },
};
