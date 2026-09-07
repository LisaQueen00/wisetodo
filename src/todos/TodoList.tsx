import { useId, useState } from "react";
import { TodoCard } from "./TodoCard";
import type { Todo } from "./types";

function TodoSection({ title, todos, expandedIds, onToggle }: {
  title: "未完成" | "已完成";
  todos: readonly Todo[];
  expandedIds: ReadonlySet<string>;
  onToggle: (todoId: string) => void;
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
          <TodoCard
            key={todo.id}
            todo={todo}
            expanded={expandedIds.has(todo.id)}
            onToggle={onToggle}
          />
        ))}
      </ul>
    </section>
  );
}

export function TodoList({ todos }: { todos: readonly Todo[] }) {
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(() => new Set());

  function toggleTodo(todoId: string) {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (next.has(todoId)) next.delete(todoId);
      else next.add(todoId);
      return next;
    });
  }

  // Stable partition: the Service already supplies priority/position order.
  const incomplete = todos.filter((todo) => !todo.completed);
  const completed = todos.filter((todo) => todo.completed);

  return (
    <div className="space-y-7">
      <TodoSection title="未完成" todos={incomplete} expandedIds={expandedIds} onToggle={toggleTodo} />
      <TodoSection title="已完成" todos={completed} expandedIds={expandedIds} onToggle={toggleTodo} />
    </div>
  );
}
