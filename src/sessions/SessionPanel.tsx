import { useCallback, useEffect, useRef, useState } from "react";
import type { SessionApi, SessionHistory, SessionStatus, SessionSummary } from "./types";
import { ChatMessages } from "./ChatMessages";
import { SessionStages } from "./SessionStages";
import { UrlAttachments } from "./UrlAttachments";
import { useFileDrops } from "./useFileDrops";
import { RunControl } from "./RunControl";
import type { LoadTodos, Todo } from "../todos/types";

const labels: Record<SessionStatus, string> = {
  ready: "待开始", running: "执行中", waiting_input: "等待补充", completed: "已完成", failed: "失败", cancelled: "已停止",
};

export function SessionPanel({ api, loadTodos, onCommitted, visible = true, onRunningChange }: { api: SessionApi; loadTodos?: LoadTodos; onCommitted?: () => void; visible?: boolean; onRunningChange?: (running: boolean) => void }) {
  const [targets, setTargets] = useState<Todo[]>([]);
  const [targetId, setTargetId] = useState("");
  const [rows, setRows] = useState<SessionSummary[]>([]);
  const [active, setActive] = useState<SessionHistory | null>(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [runEventsReady, setRunEventsReady] = useState(!api.listenRuns);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [listReady, setListReady] = useState(false);
  const request = useRef(0);
  const mutation = useRef(false);
  const composing = useRef(false);
  const [drafts, setDrafts] = useState<Record<string, { text: string; messageId: string; urls: string[]; files: string[] }>>({});
  const [notice, setNotice] = useState("");
  const draft = active ? drafts[active.id] : undefined;
  const canInput = !!active && active.status !== "completed" && active.status !== "running";
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const activeId = active?.id;
  useEffect(() => { onRunningChange?.(mutating || active?.status === "running"); }, [mutating, active?.status, onRunningChange]);
  useEffect(() => {
    let live = true;
    let sequence = 0;
    let stop: (() => void) | undefined;
    api.listenRuns?.((event) => {
      if (!live || event.session_id !== activeId) return;
      const revision = ++sequence;
      if (event.event !== "run.updated") return;
      const ticket = request.current;
      void api.get(event.session_id).then((history) => {
        if (live && revision === sequence && ticket === request.current && mutation.current) {
          setActive((previous) => previous?.id === history.id ? history : previous);
        }
      }, () => { /* Final request refresh remains authoritative if an update fails. */ });
    }).then((unlisten) => { if (live) stop = unlisten; else unlisten(); }, () => {});
    return () => { live = false; stop?.(); };
  }, [api, activeId]);
  useEffect(() => {
    if (!loadTodos || !api.executesMessages) return;
    let live = true;
    loadTodos().then((todos) => { if (live) setTargets(todos); }, () => {
      if (live) setError("读取编辑目标失败，请刷新历史后重试。");
    });
    return () => { live = false; };
  }, [loadTodos, api.executesMessages, activeId, busy, attempt]);
  const addFiles = useCallback((paths: string[]) => {
    if (!activeId || mutation.current) return;
    const messageId = crypto.randomUUID();
    setDrafts((previous) => {
      const old = previous[activeId];
      return { ...previous, [activeId]: { text: old?.text ?? "", urls: old?.urls ?? [],
        files: [...new Set([...(old?.files ?? []), ...paths])], messageId } };
    });
    setError("");
  }, [activeId]);
  useFileDrops(api, inputRef, visible && canInput && !busy && listReady, addFiles, setError);
  useEffect(() => {
    const requests = request;
    const ticket = ++request.current;
    api.list().then((sessions) => {
      if (ticket === request.current) { setRows(sessions); setListReady(true); }
    }, () => { if (ticket === request.current) setError("读取历史失败，请刷新重试。"); });
    return () => { requests.current++; };
  }, [api, attempt]);

  async function open(id: string) {
    if (mutation.current) return;
    const ticket = ++request.current;
    setActive(null);
    setNotice("");
    composing.current = false;
    setBusy(true);
    setError("");
    try {
      const history = await api.get(id);
      if (ticket === request.current) { setActive(history); setTargetId(history.target_todo_id ?? ""); }
    } catch { if (ticket === request.current) setError("加载会话失败，请重新选择或刷新历史。"); }
    finally { if (ticket === request.current) setBusy(false); }
  }
  async function change(kind: "create" | "delete" | "retry" | "send", id?: string) {
    if (mutation.current) return;
    if (kind === "send" && (!canInput || busy || !listReady || !runEventsReady || (!draft?.text.trim() && !draft?.urls.length && !draft?.files.length) || composing.current)) return;
    mutation.current = true;
    setMutating(true);
    const ticket = ++request.current;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (kind === "create") {
        const created = await api.create(label);
        if (ticket === request.current) {
          setRows((previous) => [created, ...previous.filter((row) => row.id !== created.id)]);
          setActive(created); setLabel(""); setTargetId("");
        }
      } else if (kind === "send" && id && draft) {
        const saved = targetId
          ? await api.send(id, draft.messageId, draft.text, draft.urls, draft.files, targetId)
          : await api.send(id, draft.messageId, draft.text, draft.urls, draft.files);
        if (ticket === request.current) {
          setActive(saved);
          setRows((previous) => [saved, ...previous.filter((row) => row.id !== id)]);
          setDrafts((previous) => { const next = { ...previous }; delete next[id]; return next; });
          if (saved.status === "completed") onCommitted?.();
          setNotice(api.executesMessages ? "" : "消息已保存。执行器尚未接入，暂不会生成回复或 Todo。");
        }
      } else if (kind === "retry" && id) {
        const retried = await api.retry(id);
        if (ticket === request.current) {
          setActive(retried);
          setRows((previous) => [retried, ...previous.filter((row) => row.id !== retried.id)]);
          if (retried.status === "completed") onCommitted?.();
        }
      } else if (id) {
        await api.delete(id);
        if (ticket === request.current) {
          setRows((previous) => previous.filter((row) => row.id !== id));
          setActive((previous) => previous?.id === id ? null : previous);
          setDrafts((previous) => { const next = { ...previous }; delete next[id]; return next; });
        }
      }
    } catch (failure) {
      if ((kind === "retry" || (kind === "send" && api.executesMessages)) && id && ticket === request.current) {
        try {
          const history = await api.get(id);
          if (ticket === request.current) {
            setActive(history);
            setRows((previous) => previous.map((row) => row.id === id ? history : row));
            if (kind === "send" && draft && history.messages.some((message) => message.id === draft.messageId && message.role === "user")) {
              setDrafts((previous) => { const next = { ...previous }; delete next[id]; return next; });
            }
            if (history.status === "completed") { onCommitted?.(); setError(""); return; }
            if (history.status === "cancelled" && failure === "已停止执行。") { setError(""); setNotice("已停止执行。"); return; }
          }
        } catch { /* Keep the original safe retry error below. */ }
      }
      if (ticket === request.current) setError(kind === "send"
        ? (typeof failure === "string" ? failure : "消息保存失败，输入已保留，请重试发送。") : kind === "retry"
        ? (typeof failure === "string" ? failure : "重试失败，请刷新历史检查会话状态。")
        : kind === "create" ? "新建会话失败，请重试。" : "删除会话失败，请重试。");
    }
    finally { mutation.current = false; if (ticket === request.current) { setBusy(false); setMutating(false); } }
  }

  return <>
    <RunControl api={api} executing={mutating} onReady={setRunEventsReady} />
    <form className="mb-3 flex gap-2" onSubmit={(event) => { event.preventDefault(); void change("create"); }}>
      <input aria-label="会话标签" placeholder="会话标签（可留空）" value={label} disabled={busy || !listReady}
        onChange={(event) => setLabel(event.target.value)} className="min-w-0 flex-1 rounded-lg bg-[var(--theme-chat-message-background)] p-2 text-sm" />
      <button disabled={busy || !listReady} className="shrink-0 text-sm disabled:opacity-30">新建会话</button>
    </form>
    <div className="mb-3 flex items-center justify-between text-xs text-[var(--theme-text-secondary)]">
      <span>历史会话</span>
      <button disabled={busy} onClick={() => { setError(""); setListReady(false); setAttempt((value) => value + 1); }}>刷新历史</button>
    </div>
    {error && <p role="alert" className="mb-3 text-sm text-[var(--theme-status-error)]">{error}</p>}
    {(!listReady && !error) && <p role="status">正在读取历史…</p>}
    {busy && <p role="status">正在处理会话…</p>}
    <ul aria-label="历史会话" className="max-h-48 shrink-0 space-y-2 overflow-y-auto">
      {rows.map((session) => <li key={session.id} className="flex items-center gap-2 rounded-lg bg-[var(--theme-chat-message-background)] p-2 text-sm">
        <button disabled={!listReady || mutating} aria-pressed={active?.id === session.id} onClick={() => { void open(session.id); }}
          className="min-w-0 flex-1 text-left break-words">{session.label || "新会话"}<span className="ml-2 text-xs text-[var(--theme-text-secondary)]">{labels[session.status]}</span></button>
        <button disabled={busy || !listReady || session.status === "running"} aria-label={`删除会话 ${session.label || "新会话"}`}
          onClick={() => { void change("delete", session.id); }} className="shrink-0 text-xs text-[var(--theme-text-secondary)] disabled:opacity-30">删除</button>
      </li>)}
    </ul>
    {listReady && rows.length === 0 && <p className="text-sm text-[var(--theme-text-secondary)]">暂无历史会话</p>}
    <div className="mt-4 min-h-0 flex-1 overflow-y-auto rounded-xl border border-[var(--theme-border-normal)] p-4 text-sm text-[var(--theme-text-secondary)]">
      {active ? <>
        <h3 className="text-[var(--theme-text-primary)]">{active.label || "新会话"}</h3>
        <p className="mt-2">状态：{labels[active.status]}</p>
        <p>已加载 {active.messages.length} 条消息、{active.tool_events.length} 条工具事件。</p>
        {(active.status === "failed" || active.status === "cancelled") && <div className="mt-3">
          <button disabled={busy || !listReady || !runEventsReady} onClick={() => { void change("retry", active.id); }}
            className="rounded-lg bg-[var(--theme-chat-message-background)] px-3 py-2 disabled:opacity-30">重试</button>
          <p className="mt-2 text-xs text-[var(--theme-text-secondary)]">{api.executesMessages ? "有待提交结果时只重试保存，不再调用模型；否则复用原输入重新执行。" : "复用原输入和附件。当前执行器尚未接入，暂不能实际执行。"}</p>
        </div>}
        {active.status === "completed"
          ? <p role="status" className="mt-3 rounded-lg bg-[var(--theme-chat-message-background)] p-3">此会话已完成，只读；如需继续，请新建会话。</p>
          : <p className="mt-3 text-xs">{api.executesMessages ? "发送后执行；成功生成一个 Todo 后，此会话只读。" : "发送仅保存消息，执行器尚未接入。"}</p>}
        <ChatMessages key={active.id} messages={active.messages} />
        <SessionStages history={active} />
      </> : <p>新建会话，或点击历史会话加载；不会自动恢复上次对话。</p>}
    </div>
    {notice && <p role="status" className="mt-2 text-xs text-[var(--theme-text-secondary)]">{notice}</p>}
    <form aria-label="发送消息" className="mt-4 shrink-0" onSubmit={(event) => { event.preventDefault(); void change("send", active?.id); }}>
      {api.executesMessages && active && <label className="mb-2 block text-xs">编辑目标
        <ThemedSelect aria-label="编辑目标" value={targetId} disabled={!canInput || busy || !listReady}
          className="ml-2 max-w-full rounded bg-[var(--surface-window)] p-2"
          onChange={(event) => {
            setTargetId(event.target.value);
            if (active) setDrafts((previous) => previous[active.id]
              ? { ...previous, [active.id]: { ...previous[active.id], messageId: crypto.randomUUID() } } : previous);
          }}>
          <option value="">新建 Todo</option>
          {targets.map((todo) => <option key={todo.id} value={todo.id}>{todo.topic}</option>)}
          {targetId && !targets.some((todo) => todo.id === targetId) && <option value={targetId}>原目标已不可用</option>}
        </ThemedSelect>
      </label>}
      {active && <UrlAttachments key={active.id} urls={draft?.urls ?? []} disabled={!canInput || busy || !listReady}
        onChange={(urls) => {
          const messageId = crypto.randomUUID();
          setDrafts((previous) => ({ ...previous, [active.id]: { text: previous[active.id]?.text ?? "", urls, messageId, files: previous[active.id]?.files ?? [] } }));
        }} />}
      {!!draft?.files.length && <ul aria-label="待发送文件" className="mb-2 max-h-24 space-y-1 overflow-y-auto">
        {draft.files.map((path) => <li key={path} className="flex gap-2 rounded-lg bg-[var(--theme-chat-message-background)] p-2 text-xs">
          <span className="min-w-0 flex-1 break-all">{path}</span>
          <button type="button" disabled={!canInput || busy || !listReady} aria-label={`移除文件 ${path}`}
            onClick={() => {
              if (!active) return;
              const messageId = crypto.randomUUID();
              setDrafts((previous) => ({ ...previous, [active.id]: { ...previous[active.id], files: previous[active.id].files.filter((file) => file !== path), messageId } }));
            }}>移除</button>
        </li>)}
      </ul>}
      {active && <p className="mb-1 text-xs text-[var(--theme-text-muted)]">将 PDF、Markdown 或 TXT 拖入下方文本框；仅保存路径，不读取正文。</p>}
      <textarea ref={inputRef} disabled={!canInput || busy || !listReady} readOnly={active?.status === "completed"}
        aria-label={active?.status === "completed" ? "聊天输入（会话已完成，只读）" : "聊天输入"}
        placeholder={!active ? "请先新建或选择会话" : active.status === "completed" ? "此会话已完成，请新建会话" : active.status === "running" ? "正在执行，请等待" : "输入消息；Shift+Enter 换行"}
        rows={3} value={draft?.text ?? ""}
        onChange={(event) => {
          if (!active) return;
          const text = event.target.value;
          const messageId = crypto.randomUUID();
          setDrafts((previous) => ({ ...previous, [active.id]: { text, messageId, urls: previous[active.id]?.urls ?? [], files: previous[active.id]?.files ?? [] } }));
        }}
        onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && !composing.current && event.keyCode !== 229) {
            event.preventDefault(); void change("send", active?.id);
          }
        }}
        className="w-full resize-none rounded-xl border border-[var(--theme-border-normal)] bg-[var(--theme-chat-message-background)] p-3 text-sm placeholder:text-[var(--theme-text-muted)]" />
      {canInput && <button disabled={busy || !listReady || !runEventsReady || (!draft?.text.trim() && !draft?.urls.length && !draft?.files.length)} className="mt-2 rounded-lg bg-violet-400/15 px-4 py-2 text-sm disabled:opacity-30">发送</button>}
    </form>
  </>;
}
import { ThemedSelect } from "../theme/ThemedSelect";
