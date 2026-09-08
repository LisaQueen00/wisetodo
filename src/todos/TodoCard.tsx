import { Check, ChevronRight } from "lucide-react";
import { useId, useRef, useState } from "react";
import { TodoEditor } from "./TodoEditor";
import type { Todo, TodoActions } from "./types";

export function TodoCard({ todo, expanded, onToggle, actions, editing, editLocked, onEdit, reorder }: {
  todo: Todo;
  expanded: boolean;
  onToggle: (todoId: string) => void;
  actions?: TodoActions;
  editing: boolean;
  editLocked: boolean;
  onEdit: (todoId: string | null) => void;
  reorder?: {
    previous?: string; next?: string; locked: boolean;
    start: (id: string) => void; end: () => void;
    canDrop: (todo: Todo) => boolean; drop: (todo: Todo) => void;
    dropId: (id: string) => void;
    move: (id: string, targetId: string) => void;
  };
}) {
  const panelId = useId();
  const pointer = useRef<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(false);
  const [savingItem, setSavingItem] = useState(false);
  const [completionError, setCompletionError] = useState(false);

  async function setCompleted(itemId: string, completed: boolean) {
    if (!actions || savingItem || deleting || editLocked) return;
    setSavingItem(true);
    setCompletionError(false);
    try {
      actions.onSaved(await actions.mutations.setItemCompleted(todo.id, itemId, completed));
    } catch { setCompletionError(true); }
    finally { setSavingItem(false); }
  }

  async function remove() {
    if (!actions || deleting || savingItem || editLocked) return;
    setDeleting(true);
    setError(false);
    try {
      await actions.mutations.delete(todo.id);
      actions.onDeleted(todo.id);
    } catch { setError(true); }
    finally { setDeleting(false); }
  }

  if (editing && actions) return (
    <li className="todo-card rounded-2xl border p-4" data-priority={todo.priority}
      data-completed={todo.completed} data-editing="true">
      <TodoEditor todo={todo} mutations={actions.mutations} onSaved={actions.onSaved} onClose={() => onEdit(null)} />
    </li>
  );

  return (
    <li data-todo-id={todo.id} className="todo-card rounded-2xl border p-4" data-priority={todo.priority}
      data-completed={todo.completed}
      onDragOver={(event) => {
        if (reorder?.canDrop(todo)) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; }
      }}
      onDrop={(event) => { if (reorder?.canDrop(todo)) { event.preventDefault(); reorder.drop(todo); } }}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 flex-1 font-medium">
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={panelId}
            onClick={() => onToggle(todo.id)}
            className="flex w-full cursor-pointer items-start gap-2 rounded-md text-left hover:text-white"
          >
            <ChevronRight
              aria-hidden="true"
              focusable="false"
              className={`mt-1 size-4 shrink-0 text-white/50 transition-transform motion-reduce:transition-none ${expanded ? "rotate-90" : ""}`}
            />
            <span className="todo-title min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
              {todo.topic}
            </span>
          </button>
        </h3>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className="todo-priority rounded-md px-2 py-1 text-xs">
            {todo.priority === 1 ? "高优先级" : "普通"}
          </span>
          {todo.completed && <span className="flex items-center gap-1 text-xs text-[var(--todo-completed)]">
            <Check aria-hidden="true" className="size-3.5" />已完成
          </span>}
        </div>
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
      {actions && (
        <div className="mt-3 flex gap-3 text-xs text-white/65">
          <button type="button" className="disabled:opacity-30" disabled={deleting || savingItem || editLocked} aria-label={`编辑 ${todo.topic}`} onClick={() => onEdit(todo.id)}>编辑</button>
          <button type="button" className="disabled:opacity-30" disabled={deleting || savingItem || editLocked} aria-label={`删除 ${todo.topic}`} onClick={() => { void remove(); }}>
            {deleting ? "正在删除…" : "删除 Todo"}
          </button>
          {error && <p role="alert">删除失败，请重试。</p>}
        </div>
      )}
      {reorder && (
        <div className="mt-3 flex gap-3 text-xs text-white/60">
          <button type="button" draggable={false}
            disabled={editLocked || deleting || savingItem || reorder.locked}
            aria-label={`拖动排序 ${todo.topic}`} className="touch-none cursor-grab disabled:opacity-30"
            onPointerDown={(event) => {
              if (event.button !== 0 || editLocked || deleting || savingItem || reorder.locked) return;
              event.preventDefault();
              pointer.current = event.pointerId;
              event.currentTarget.setPointerCapture?.(event.pointerId);
              reorder.start(todo.id);
            }}
            onPointerMove={(event) => {
              if (pointer.current === null) return;
              const scroll = event.currentTarget.closest('[aria-label="Todo 列表滚动区"]');
              if (scroll) {
                const bounds = scroll.getBoundingClientRect();
                if (event.clientY < bounds.top + 40) scroll.scrollTop -= 16;
                else if (event.clientY > bounds.bottom - 40) scroll.scrollTop += 16;
              }
            }}
            onPointerUp={(event) => {
              if (pointer.current === null) return;
              pointer.current = null;
              const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-todo-id]");
              if (target?.dataset.todoId) reorder.dropId(target.dataset.todoId);
              else reorder.end();
            }}
            onPointerCancel={() => { pointer.current = null; reorder.end(); }}
            onLostPointerCapture={() => { pointer.current = null; reorder.end(); }}
            onKeyDown={(event) => { if (event.key === "Escape") { pointer.current = null; reorder.end(); } }}
            onDragStart={(event) => {
              event.dataTransfer.setData("text/plain", todo.id);
              event.dataTransfer.effectAllowed = "move";
              reorder.start(todo.id);
            }} onDragEnd={reorder.end}>排序</button>
          <button type="button" aria-label={`上移 ${todo.topic}`} className="disabled:opacity-30"
            disabled={editLocked || deleting || savingItem || reorder.locked || !reorder.previous}
            onClick={() => { if (reorder.previous) reorder.move(todo.id, reorder.previous); }}>上移</button>
          <button type="button" aria-label={`下移 ${todo.topic}`} className="disabled:opacity-30"
            disabled={editLocked || deleting || savingItem || reorder.locked || !reorder.next}
            onClick={() => { if (reorder.next) reorder.move(todo.id, reorder.next); }}>下移</button>
        </div>
      )}
      {savingItem && <p role="status" className="mt-2 text-xs text-white/50">正在保存完成状态…</p>}
      {completionError && <p role="alert" className="mt-2 text-xs text-red-300">完成状态保存失败，未更改原状态，请重新勾选重试。</p>}
      <div id={panelId} hidden={!expanded}>
        {expanded && (
          <ol
            aria-label={`${todo.topic}的子项`}
            className="mt-4 list-decimal space-y-2 border-t border-white/10 pt-4 pl-6 text-sm text-white/70 marker:text-white/40"
          >
            {todo.items.map((item) => (
              <li key={item.id} className="pl-1 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                <div className="flex items-start justify-between gap-3">
                  <span className={`min-w-0 flex-1 ${item.completed ? "text-[var(--todo-completed)] line-through decoration-current/40" : ""}`}>{item.topic}</span>
                  <input
                    type="checkbox"
                    aria-label={`${item.topic}完成状态`}
                    checked={item.completed}
                    disabled={!actions || savingItem || deleting || editLocked}
                    onChange={(event) => { void setCompleted(item.id, event.currentTarget.checked); }}
                    className="mt-1 size-4 shrink-0 cursor-pointer accent-[var(--todo-accent)] disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </li>
  );
}
