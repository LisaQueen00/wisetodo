import { invoke } from "@tauri-apps/api/core";
import type { LoadTodos, Todo, TodoItem } from "./types";

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
