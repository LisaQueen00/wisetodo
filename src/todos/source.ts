import { isTauri } from "@tauri-apps/api/core";
import { loadDesktopTodos } from "./desktop";
import type { LoadTodos } from "./types";

export async function resolveTodoSource(search: string): Promise<{
  loadTodos?: LoadTodos;
  preview: boolean;
}> {
  const preview = import.meta.env.DEV && new URLSearchParams(search).get("preview") === "todos";
  if (preview) {
    return { loadTodos: (await import("./preview")).loadPreviewTodos, preview: true };
  }
  return { loadTodos: isTauri() ? loadDesktopTodos : undefined, preview: false };
}
