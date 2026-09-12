import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { TodoList } from "./TodoList";
import { TodoEditor } from "./TodoEditor";
import type { LoadTodos, Todo, TodoMutations } from "./types";

type State = { source: LoadTodos; attempt: number } & (
  { status: "error" } | { status: "ready"; todos: Todo[] }
);

export function TodoWorkspace({ loadTodos, mutations, refreshToken = 0 }: { loadTodos: LoadTodos; mutations?: TodoMutations; refreshToken?: number }) {
  const [state, setState] = useState<State | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [creating, setCreating] = useState(false);
  const pending = useRef(0);
  const sorting = useRef(false);
  const [busy, setBusy] = useState(false);
  const guardedMutations = useMemo<TodoMutations | undefined>(() => {
    if (!mutations) return undefined;
    async function write<T>(operation: () => Promise<T>, reorder = false): Promise<T> {
      if (sorting.current || (reorder && pending.current > 0)) throw new Error("Write in progress");
      pending.current++;
      sorting.current = reorder;
      setBusy(true);
      try { return await operation(); }
      finally {
        pending.current--;
        if (reorder) sorting.current = false;
        setBusy(pending.current > 0);
      }
    }
    return {
      create: (draft) => write(() => mutations.create(draft)),
      update: (id, draft) => write(() => mutations.update(id, draft)),
      delete: (id) => write(() => mutations.delete(id)),
      setItemCompleted: (id, itemId, completed) => write(() => mutations.setItemCompleted(id, itemId, completed)),
      move: (id, targetId) => write(async () => {
        const todos = await mutations.move(id, targetId);
        setState((previous) => previous?.status === "ready" && previous.source === loadTodos
          ? { ...previous, todos } : previous);
        return todos;
      }, true),
    };
  }, [mutations, loadTodos]);
  const onSaved = useCallback((todo: Todo) => {
    setState((previous) => {
      if (!previous || previous.status !== "ready" || previous.source !== loadTodos) return previous;
      const todos = [...previous.todos.filter((row) => row.id !== todo.id), todo];
      todos.sort((a, b) => Number(a.completed) - Number(b.completed) || b.priority - a.priority
        || a.position - b.position || a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
      return { ...previous, todos };
    });
  }, [loadTodos]);
  const onDeleted = useCallback((id: string) => {
    setState((previous) => previous?.status === "ready" && previous.source === loadTodos
      ? { ...previous, todos: previous.todos.filter((todo) => todo.id !== id) } : previous);
  }, [loadTodos]);
  const actions = useMemo(() => mutations
    ? { mutations: guardedMutations!, onSaved, onDeleted, busy: busy || creating } : undefined,
    [mutations, guardedMutations, onSaved, onDeleted, busy, creating]);
  useEffect(() => {
    let active = true;
    Promise.resolve().then(loadTodos).then(
      (todos) => { if (active) setState({ source: loadTodos, attempt, status: "ready", todos }); },
      () => { if (active) setState({ source: loadTodos, attempt, status: "error" }); },
    );
    return () => { active = false; };
  }, [loadTodos, attempt, refreshToken]);

  if (!state || state.source !== loadTodos || state.attempt !== attempt) {
    return <p role="status">正在读取 Todo…</p>;
  }
  if (state.status === "error") return (
    <div role="alert" className="rounded-xl border border-[var(--theme-border-normal)] p-6">
      <p>读取 Todo 失败，请重试。</p>
      <button className="mt-3 rounded-lg bg-[var(--theme-chat-message-background)] px-3 py-2" onClick={() => {
        setAttempt((value) => value + 1);
      }}>重新读取</button>
    </div>
  );
  return (
    <>
      {mutations && (
        <div className="mb-4">
          {creating ? (
            <div className="rounded-xl border border-[var(--theme-border-normal)] p-4">
              <TodoEditor mutations={guardedMutations!} onSaved={onSaved} onClose={() => setCreating(false)} />
            </div>
          ) : <button disabled={busy} className="rounded-md bg-[var(--theme-chat-message-background)] px-3 py-2 text-sm disabled:opacity-30" onClick={() => setCreating(true)}>新增 Todo</button>}
        </div>
      )}
      <p role="status" className="mb-4 text-xs text-[var(--theme-text-muted)]">共 {state.todos.length} 个 Todo</p>
      {state.todos.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-[var(--theme-border-normal)] p-8 text-center">
          <p>还没有 Todo</p><p className="mt-2 text-sm text-[var(--theme-text-muted)]">任务创建后会显示在这里。</p>
        </div>
      ) : null}
      <TodoList todos={state.todos} actions={actions} />
    </>
  );
}
