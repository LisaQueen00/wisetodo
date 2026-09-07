import { ChevronRight } from "lucide-react";
import { useId, useState } from "react";
import { TodoEditor } from "./TodoEditor";
import type { Todo, TodoActions } from "./types";

export function TodoCard({ todo, expanded, onToggle, actions, editing, editLocked, onEdit }: {
  todo: Todo;
  expanded: boolean;
  onToggle: (todoId: string) => void;
  actions?: TodoActions;
  editing: boolean;
  editLocked: boolean;
  onEdit: (todoId: string | null) => void;
}) {
  const panelId = useId();
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
    <li className="rounded-2xl border border-white/20 bg-[var(--surface-todo)] p-4">
      <TodoEditor todo={todo} mutations={actions.mutations} onSaved={actions.onSaved} onClose={() => onEdit(null)} />
    </li>
  );

  return (
    <li className="rounded-2xl border border-white/10 bg-[var(--surface-todo)] p-4">
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
            <span className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
              {todo.topic}
            </span>
          </button>
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
      {actions && (
        <div className="mt-3 flex gap-3 text-xs text-white/65">
          <button type="button" className="disabled:opacity-30" disabled={deleting || savingItem || editLocked} aria-label={`编辑 ${todo.topic}`} onClick={() => onEdit(todo.id)}>编辑</button>
          <button type="button" className="disabled:opacity-30" disabled={deleting || savingItem || editLocked} aria-label={`删除 ${todo.topic}`} onClick={() => { void remove(); }}>
            {deleting ? "正在删除…" : "删除 Todo"}
          </button>
          {error && <p role="alert">删除失败，请重试。</p>}
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
                  <span className="min-w-0 flex-1">{item.topic}</span>
                  <input
                    type="checkbox"
                    aria-label={`${item.topic}完成状态`}
                    checked={item.completed}
                    disabled={!actions || savingItem || deleting || editLocked}
                    onChange={(event) => { void setCompleted(item.id, event.currentTarget.checked); }}
                    className="mt-1 size-4 shrink-0 cursor-pointer accent-violet-400 disabled:cursor-not-allowed disabled:opacity-50"
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
