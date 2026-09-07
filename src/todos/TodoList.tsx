import { useId } from "react";
import type { Todo } from "./types";

function TodoSection({ title, todos }: {
  title: "未完成" | "已完成";
  todos: readonly Todo[];
}) {
  const headingId = useId();
  if (todos.length === 0) return null;

  return (
    <section aria-labelledby={headingId}>
      <header className="mb-3 flex items-center gap-2">
        <h2 id={headingId} className="text-sm font-medium text-white/70">{title}</h2>
        <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs tabular-nums text-white/45">
          {todos.length}
        </span>
      </header>
      <ul aria-label={`${title} Todo`} className="space-y-3">
        {todos.map((todo) => (
          <li key={todo.id} className="rounded-2xl border border-white/10 bg-[var(--surface-todo)] p-4">
            <div className="flex items-start justify-between gap-3">
              <h3 className="min-w-0 flex-1 whitespace-pre-wrap break-words font-medium [overflow-wrap:anywhere]">
                {todo.topic}
              </h3>
              <span className="shrink-0 rounded-md bg-white/5 px-2 py-1 text-xs text-white/55">
                {todo.priority === 1 ? "高优先级" : "普通"}
              </span>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <progress
                aria-label={`${todo.topic}的进度`}
                value={todo.progress}
                max={1}
                className="h-1.5 min-w-0 flex-1"
              />
              <span className="shrink-0 text-xs tabular-nums text-white/50">
                {Math.round(todo.progress * 100)}% · {todo.items.length} 个子项
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function TodoList({ todos }: { todos: readonly Todo[] }) {
  // Stable partition: the Service already supplies priority/position order.
  const incomplete = todos.filter((todo) => !todo.completed);
  const completed = todos.filter((todo) => todo.completed);

  return (
    <div className="space-y-7">
      <TodoSection title="未完成" todos={incomplete} />
      <TodoSection title="已完成" todos={completed} />
    </div>
  );
}
