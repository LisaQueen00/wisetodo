import { ChevronRight } from "lucide-react";
import { useId } from "react";
import type { Todo } from "./types";

export function TodoCard({ todo, expanded, onToggle }: {
  todo: Todo;
  expanded: boolean;
  onToggle: (todoId: string) => void;
}) {
  const panelId = useId();

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
      <div id={panelId} hidden={!expanded}>
        {expanded && (
          <ol
            aria-label={`${todo.topic}的子项`}
            className="mt-4 list-decimal space-y-2 border-t border-white/10 pt-4 pl-6 text-sm text-white/70 marker:text-white/40"
          >
            {todo.items.map((item) => (
              <li key={item.id} className="pl-1 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {item.topic}
              </li>
            ))}
          </ol>
        )}
      </div>
    </li>
  );
}
