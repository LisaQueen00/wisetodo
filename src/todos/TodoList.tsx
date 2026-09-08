import { useId, useRef, useState } from "react";
import { TodoCard } from "./TodoCard";
import type { Todo, TodoActions } from "./types";

interface Sorting {
  start: (id: string) => void;
  end: () => void;
  canDrop: (todo: Todo) => boolean;
  drop: (todo: Todo) => void;
  dropId: (id: string) => void;
  move: (id: string, targetId: string) => void;
  locked: boolean;
}

function TodoSection({ title, todos, expandedIds, onToggle, actions, editingId, onEdit, sorting }: {
  title: "未完成" | "已完成";
  todos: readonly Todo[];
  expandedIds: ReadonlySet<string>;
  onToggle: (todoId: string) => void;
  actions?: TodoActions;
  editingId: string | null;
  onEdit: (todoId: string | null) => void;
  sorting: Sorting;
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
        {todos.map((todo, index) => (
          <TodoCard
            key={todo.id}
            todo={todo}
            expanded={expandedIds.has(todo.id)}
            onToggle={onToggle}
            actions={actions}
            editing={editingId === todo.id}
            editLocked={editingId !== null || !!actions?.busy || sorting.locked}
            onEdit={onEdit}
            reorder={actions ? {
              ...sorting,
              previous: todos[index - 1]?.priority === todo.priority ? todos[index - 1].id : undefined,
              next: todos[index + 1]?.priority === todo.priority ? todos[index + 1].id : undefined,
            } : undefined}
          />
        ))}
      </ul>
    </section>
  );
}

export function TodoList({ todos, actions }: { todos: readonly Todo[]; actions?: TodoActions }) {
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const dragged = useRef<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const locked = saving || !!actions?.busy || editingId !== null;
  const canDrop = (target: Todo) => {
    const source = todos.find((todo) => todo.id === dragged.current);
    return !locked && !!source && source.id !== target.id
      && source.priority === target.priority && source.completed === target.completed;
  };
  async function move(id: string, targetId: string) {
    if (!actions || locked || id === targetId) return;
    setSaving(true);
    setError(false);
    try { await actions.mutations.move(id, targetId); }
    catch { setError(true); }
    finally { setSaving(false); }
  }
  const sorting: Sorting = {
    locked,
    start: (id) => { dragged.current = id; setDragging(true); },
    end: () => { dragged.current = null; setDragging(false); },
    canDrop,
    drop: (target) => {
      if (canDrop(target) && dragged.current) void move(dragged.current, target.id);
      dragged.current = null;
      setDragging(false);
    },
    move: (id, targetId) => { void move(id, targetId); },
    dropId: (id) => {
      const target = todos.find((todo) => todo.id === id);
      if (target && canDrop(target) && dragged.current) void move(dragged.current, target.id);
      dragged.current = null; setDragging(false);
    },
  };

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
      {actions && <p className="text-xs text-white/45">拖动“排序”到同状态、同优先级的任务上，或使用上移 / 下移。</p>}
      {dragging && <p role="status">松开后移动到目标位置；不能跨完成状态或优先级。</p>}
      {saving && <p role="status">正在保存排序…</p>}
      {error && <p role="alert">排序保存失败，列表未更改，请重试。</p>}
      <TodoSection title="未完成" todos={incomplete} expandedIds={expandedIds} onToggle={toggleTodo}
        actions={actions} editingId={editingId} onEdit={setEditingId} sorting={sorting} />
      <TodoSection title="已完成" todos={completed} expandedIds={expandedIds} onToggle={toggleTodo}
        actions={actions} editingId={editingId} onEdit={setEditingId} sorting={sorting} />
    </div>
  );
}
