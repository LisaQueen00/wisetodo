import { useEffect, useState } from "react";
import { TodoList } from "./TodoList";
import type { LoadTodos, Todo } from "./types";

type State = { source: LoadTodos; attempt: number } & (
  { status: "error" } | { status: "ready"; todos: Todo[] }
);

export function TodoWorkspace({ loadTodos }: { loadTodos: LoadTodos }) {
  const [state, setState] = useState<State | null>(null);
  const [attempt, setAttempt] = useState(0);
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
      <p role="status" className="mb-4 text-xs text-white/45">共 {state.todos.length} 个 Todo</p>
      {state.todos.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-white/15 p-8 text-center">
          <p>还没有 Todo</p><p className="mt-2 text-sm text-white/45">任务创建后会显示在这里。</p>
        </div>
      ) : (
        <TodoList todos={state.todos} />
      )}
    </>
  );
}
