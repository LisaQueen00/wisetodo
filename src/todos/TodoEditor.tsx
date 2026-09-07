import { useEffect, useRef, useState } from "react";
import { DEFAULT_SAVE_DELAY_MS, DebouncedSave } from "../lib/debouncedSave";
import type { Todo, TodoDraft, TodoMutations } from "./types";

type Draft = Omit<TodoDraft, "items"> & { items: { key: string; topic: string }[] };
const inputStyle = "w-full rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm";

function validate(draft: Draft): string | undefined {
  if (!draft.topic.trim()) return "请输入 Todo 标题。";
  if (draft.items.length < 2) return "至少保留两个子项。";
  if (draft.items.some((item) => !item.topic.trim())) return "请填写每个子项的内容。";
}

export function TodoEditor({ todo, mutations, onSaved, onClose }: {
  todo?: Todo;
  mutations: TodoMutations;
  onSaved: (todo: Todo) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => ({
    topic: todo?.topic ?? "", priority: todo?.priority ?? 0,
    items: todo ? todo.items.map((item) => ({ key: item.id, topic: item.topic }))
      : [0, 1].map((i) => ({ key: `new-${i}`, topic: "" })),
  }));
  const current = useRef(draft);
  // UI row keys stay stable; each successful write may assign fresh database IDs.
  const ids = useRef(new Map(todo?.items.map((item) => [item.id, item.id])));
  const saved = useRef(todo);
  const dirty = useRef(false);
  const composing = useRef(false);
  const finishing = useRef(false);
  const inFlight = useRef<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [status, setStatus] = useState("");
  const todoId = todo?.id;

  const autosave = useRef<DebouncedSave<Draft> | null>(null);
  useEffect(() => {
    const saver = new DebouncedSave<Draft>(async (snapshot) => {
      inFlight.current = snapshot;
      setBusy(true);
      setStatus("正在保存…");
      setError(undefined);
      try {
        const payload: TodoDraft = {
          topic: snapshot.topic, priority: snapshot.priority,
          items: snapshot.items.map((item) => ({ id: ids.current.get(item.key), topic: item.topic })),
        };
        const result = saved.current
          ? await mutations.update(saved.current.id, payload)
          : await mutations.create(payload);
        saved.current = result;
        snapshot.items.forEach((item, index) => ids.current.set(item.key, result.items[index].id));
        // A response must not replace text typed while that request was in flight.
        if (current.current === snapshot) {
          const normalized = {
            topic: result.topic, priority: result.priority,
            items: result.items.map((item, index) => ({ key: snapshot.items[index].key, topic: item.topic })),
          };
          current.current = normalized;
          setDraft(normalized);
          dirty.current = false;
          setStatus("已保存");
          onSaved(result);
        }
      } catch {
        setStatus("");
        setError("保存失败，输入已保留。请重试保存。");
        throw new Error("Todo save failed");
      } finally {
        inFlight.current = null;
        setBusy(false);
      }
    }, DEFAULT_SAVE_DELAY_MS, () => undefined);
    autosave.current = saver;
    return () => { saver.cancel(); autosave.current = null; };
  }, [mutations, onSaved]);

  function change(next: Draft) {
    current.current = next;
    dirty.current = true;
    setDraft(next);
    const problem = validate(next);
    setError(problem);
    setStatus(problem ? "" : "尚未保存");
    autosave.current?.cancel();
    if (todoId && !problem && !composing.current) autosave.current?.schedule(next);
  }

  async function finish(close: boolean) {
    if (finishing.current || composing.current) return;
    const problem = validate(current.current);
    if (problem) { setError(problem); return; }
    finishing.current = true;
    try {
      if (dirty.current && inFlight.current !== current.current) autosave.current?.schedule(current.current);
      await autosave.current?.flush();
      if (close && !dirty.current) onClose();
    } catch { /* The draft and error remain available for retry. */ }
    finally { finishing.current = false; }
  }

  return (
    <form aria-label={todo ? `编辑 ${todo.topic}` : "新增 Todo"} className="space-y-3"
      onSubmit={(event) => { event.preventDefault(); void finish(true); }}
      onBlur={(event) => {
        if (todoId && !event.currentTarget.contains(event.relatedTarget)) void finish(false);
      }}
      onCompositionStart={() => { composing.current = true; autosave.current?.cancel(); }}
      onCompositionEnd={() => { composing.current = false; change(current.current); }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && event.nativeEvent.isComposing) event.preventDefault();
      }}>
      <label className="block text-sm">Todo 标题
        <input className={inputStyle} value={draft.topic} onChange={(e) => change({ ...draft, topic: e.target.value })} />
      </label>
      <label className="block text-sm">优先级
        <select className={inputStyle} value={draft.priority} onChange={(e) => change({ ...draft, priority: Number(e.target.value) as 0 | 1 })}>
          <option value={0}>普通</option><option value={1}>高优先级</option>
        </select>
      </label>
      <ol className="list-decimal space-y-2 pl-6">
        {draft.items.map((item, index) => (
          <li key={item.key}>
            <div className="flex gap-2">
              <input aria-label={`子项 ${index + 1}`} className={inputStyle} value={item.topic}
                onChange={(e) => change({ ...draft, items: draft.items.map((row) => row.key === item.key ? { ...row, topic: e.target.value } : row) })} />
              <button type="button" aria-label={`删除子项 ${index + 1}`} disabled={draft.items.length <= 2}
                className="shrink-0 px-2 text-sm disabled:opacity-30"
                onClick={() => change({ ...draft, items: draft.items.filter((row) => row.key !== item.key) })}>删除</button>
            </div>
          </li>
        ))}
      </ol>
      <p className="text-xs text-white/50">至少保留两个子项</p>
      <button type="button" className="rounded-md bg-white/10 px-3 py-2 text-sm"
        onClick={() => change({ ...draft, items: [...draft.items, { key: crypto.randomUUID(), topic: "" }] })}>添加子项</button>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      <p role="status" className="text-xs text-white/60">{status}</p>
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={busy} className="rounded-md bg-white/15 px-3 py-2 text-sm disabled:opacity-40">
          {todo ? "完成编辑" : "创建 Todo"}
        </button>
        {error && todo && <button type="button" disabled={busy} onClick={() => { void finish(false); }}>重试保存</button>}
        <button type="button" disabled={busy} className="px-3 py-2 text-sm disabled:opacity-40" onClick={() => {
          autosave.current?.cancel();
          if (saved.current) onSaved(saved.current);
          onClose();
        }}>{todo ? "放弃未保存修改" : "取消新增"}</button>
      </div>
    </form>
  );
}
