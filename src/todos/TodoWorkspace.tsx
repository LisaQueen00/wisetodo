import { useEffect, useState } from "react";
import type { LoadTodos, Todo } from "./types";

type State = { status: "loading" } | { status: "error" } | { status: "ready"; todos: Todo[] };

export function TodoWorkspace({ loadTodos }: { loadTodos: LoadTodos }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.resolve().then(loadTodos).then(
      (todos) => { if (active) setState({ status: "ready", todos }); },
      () => { if (active) setState({ status: "error" }); },
    );
    return () => { active = false; };
  }, [loadTodos, attempt]);

  if (state.status === "loading") return <p role="status">正在读取 Todo…</p>;
  if (state.status === "error") return (
    <div role="alert" className="rounded-xl border border-white/15 p-6">
      <p>读取 Todo 失败，请重试。</p>
      <button className="mt-3 rounded-lg bg-white/10 px-3 py-2" onClick={() => {
        setState({ status: "loading" });
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
        <ul aria-label="全部 Todo" className="space-y-3">
          {state.todos.map((todo) => (
            <li key={todo.id} className="rounded-2xl border border-white/10 bg-[var(--surface-todo)] p-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="min-w-0 flex-1 whitespace-pre-wrap break-words font-medium [overflow-wrap:anywhere]">{todo.topic}</h2>
                <span className="shrink-0 rounded-md bg-white/5 px-2 py-1 text-xs text-white/55">{todo.priority === 1 ? "高优先级" : "普通"}</span>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <progress aria-label={`${todo.topic}的进度`} value={todo.progress} max={1} className="h-1.5 min-w-0 flex-1" />
                <span className="shrink-0 text-xs tabular-nums text-white/50">{Math.round(todo.progress * 100)}% · {todo.items.length} 个子项</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
