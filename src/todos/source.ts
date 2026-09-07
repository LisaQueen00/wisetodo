import { isTauri } from "@tauri-apps/api/core";
import { desktopMutations, loadDesktopTodos } from "./desktop";
import type { LoadTodos, TodoMutations } from "./types";

export async function resolveTodoSource(search: string): Promise<{
  loadTodos?: LoadTodos;
  mutations?: TodoMutations;
  preview: boolean;
}> {
  const preview = import.meta.env.DEV && new URLSearchParams(search).get("preview") === "todos";
  if (preview) {
    return { loadTodos: (await import("./preview")).loadPreviewTodos, preview: true };
  }
  return isTauri()
    ? { loadTodos: loadDesktopTodos, mutations: desktopMutations, preview: false }
    : { loadTodos: undefined, preview: false };
}
