import { useEffect, useRef, useState } from "react";
import type { SessionApi, SessionHistory, SessionStatus, SessionSummary } from "./types";

const labels: Record<SessionStatus, string> = {
  ready: "待开始", running: "执行中", waiting_input: "等待补充", completed: "已完成", failed: "失败", cancelled: "已停止",
};

export function SessionPanel({ api }: { api: SessionApi }) {
  const [rows, setRows] = useState<SessionSummary[]>([]);
  const [active, setActive] = useState<SessionHistory | null>(null);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [mutating, setMutating] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [listReady, setListReady] = useState(false);
  const request = useRef(0);
  const mutation = useRef(false);
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
    setBusy(true);
    setError("");
    try {
      const history = await api.get(id);
      if (ticket === request.current) setActive(history);
    } catch { if (ticket === request.current) setError("加载会话失败，请重新选择或刷新历史。"); }
    finally { if (ticket === request.current) setBusy(false); }
  }
  async function change(kind: "create" | "delete", id?: string) {
    if (mutation.current) return;
    mutation.current = true;
    setMutating(true);
    const ticket = ++request.current;
    setBusy(true);
    setError("");
    try {
      if (kind === "create") {
        const created = await api.create(label);
        if (ticket === request.current) {
          setRows((previous) => [created, ...previous.filter((row) => row.id !== created.id)]);
          setActive(created); setLabel("");
        }
      } else if (id) {
        await api.delete(id);
        if (ticket === request.current) {
          setRows((previous) => previous.filter((row) => row.id !== id));
          setActive((previous) => previous?.id === id ? null : previous);
        }
      }
    } catch { if (ticket === request.current) setError(kind === "create" ? "新建会话失败，请重试。" : "删除会话失败，请重试。"); }
    finally { mutation.current = false; if (ticket === request.current) { setBusy(false); setMutating(false); } }
  }

  return <>
    <form className="mb-3 flex gap-2" onSubmit={(event) => { event.preventDefault(); void change("create"); }}>
      <input aria-label="会话标签" placeholder="会话标签（可留空）" value={label} disabled={busy || !listReady}
        onChange={(event) => setLabel(event.target.value)} className="min-w-0 flex-1 rounded-lg bg-white/5 p-2 text-sm" />
      <button disabled={busy || !listReady} className="shrink-0 text-sm disabled:opacity-30">新建会话</button>
    </form>
    <div className="mb-3 flex items-center justify-between text-xs text-white/60">
      <span>历史会话</span>
      <button disabled={busy} onClick={() => { setError(""); setListReady(false); setAttempt((value) => value + 1); }}>刷新历史</button>
    </div>
    {error && <p role="alert" className="mb-3 text-sm text-red-300">{error}</p>}
    {(!listReady && !error) && <p role="status">正在读取历史…</p>}
    {busy && <p role="status">正在处理会话…</p>}
    <ul aria-label="历史会话" className="max-h-48 shrink-0 space-y-2 overflow-y-auto">
      {rows.map((session) => <li key={session.id} className="flex items-center gap-2 rounded-lg bg-white/5 p-2 text-sm">
        <button disabled={!listReady || mutating} aria-pressed={active?.id === session.id} onClick={() => { void open(session.id); }}
          className="min-w-0 flex-1 text-left break-words">{session.label || "新会话"}<span className="ml-2 text-xs text-white/50">{labels[session.status]}</span></button>
        <button disabled={busy || !listReady || session.status === "running"} aria-label={`删除会话 ${session.label || "新会话"}`}
          onClick={() => { void change("delete", session.id); }} className="shrink-0 text-xs text-white/60 disabled:opacity-30">删除</button>
      </li>)}
    </ul>
    {listReady && rows.length === 0 && <p className="text-sm text-white/50">暂无历史会话</p>}
    <div className="mt-4 min-h-0 flex-1 overflow-y-auto rounded-xl border border-white/10 p-4 text-sm text-white/65">
      {active ? <>
        <h3 className="text-white">{active.label || "新会话"}</h3>
        <p className="mt-2">状态：{labels[active.status]}</p>
        <p>已加载 {active.messages.length} 条消息、{active.tool_events.length} 条工具事件。</p>
        {active.status === "completed"
          ? <p role="status" className="mt-3 rounded-lg bg-white/5 p-3">此会话已完成，只读；如需继续，请新建会话。</p>
          : <p className="mt-3">消息展示与发送功能待接入。</p>}
      </> : <p>新建会话，或点击历史会话加载；不会自动恢复上次对话。</p>}
    </div>
    <textarea disabled readOnly={active?.status === "completed"}
      aria-label={active?.status === "completed" ? "聊天输入（会话已完成，只读）" : "聊天输入（待接入）"}
      placeholder={active?.status === "completed" ? "此会话已完成，请新建会话" : "聊天功能待接入"} rows={3}
      className="mt-4 w-full shrink-0 resize-none rounded-xl border border-white/10 bg-white/5 p-3 text-sm placeholder:text-white/30" />
  </>;
}
