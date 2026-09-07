import { useCallback, useEffect, useMemo, useState } from "react";
import { TodoList } from "./TodoList";
import { TodoEditor } from "./TodoEditor";
import type { LoadTodos, Todo, TodoMutations } from "./types";

type State = { source: LoadTodos; attempt: number } & (
  { status: "error" } | { status: "ready"; todos: Todo[] }
);

export function TodoWorkspace({ loadTodos, mutations }: { loadTodos: LoadTodos; mutations?: TodoMutations }) {
  const [state, setState] = useState<State | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [creating, setCreating] = useState(false);
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
  const actions = useMemo(() => mutations ? { mutations, onSaved, onDeleted } : undefined,
    [mutations, onSaved, onDeleted]);
  useEffect(() => {
    let active = true;
    Promise.resolve().then(loadTodos).then(
      (todos) => { if (active) setState({ source: loadTodos, attempt, status: "ready", todos }); },
      () => { if (active) setState({ source: loadTodos, attempt, status: "error" }); },
    );
    return () => { active = false; };
  }, [loadTodos, attempt]);

  if (!state || state.source !== loadTodos || state.attempt !== attempt) {
    return <p role="status">正在读取 Todo…</p>;
  }
  if (state.status === "error") return (
    <div role="alert" className="rounded-xl border border-white/15 p-6">
      <p>读取 Todo 失败，请重试。</p>
      <button className="mt-3 rounded-lg bg-white/10 px-3 py-2" onClick={() => {
        setAttempt((value) => value + 1);
      }}>重新读取</button>
    </div>
  );
  return (
    <>
      {mutations && (
        <div className="mb-4">
          {creating ? (
            <div className="rounded-xl border border-white/15 p-4">
              <TodoEditor mutations={mutations} onSaved={onSaved} onClose={() => setCreating(false)} />
            </div>
          ) : <button className="rounded-md bg-white/10 px-3 py-2 text-sm" onClick={() => setCreating(true)}>新增 Todo</button>}
        </div>
      )}
      <p role="status" className="mb-4 text-xs text-white/45">共 {state.todos.length} 个 Todo</p>
      {state.todos.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/15 p-8 text-center">
          <p>还没有 Todo</p><p className="mt-2 text-sm text-white/45">任务创建后会显示在这里。</p>
        </div>
      ) : (
        <TodoList todos={state.todos} actions={actions} />
      )}
    </>
  );
}
