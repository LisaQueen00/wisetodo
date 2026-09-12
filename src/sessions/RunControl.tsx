import { useEffect, useRef, useState } from "react";
import type { RunEvent, SessionApi } from "./types";

export function RunControl({ api, executing, onReady }: { api: SessionApi; executing: boolean; onReady?: (ready: boolean) => void }) {
  const [run, setRun] = useState<RunEvent | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const cancelling = useRef(false);
  useEffect(() => {
    let active = true;
    let stop: (() => void) | undefined;
    api.listenRuns?.((event) => {
      if (!active) return;
      if (event.event === "run.started") { setRun(event); setError(""); setPending(false); cancelling.current = false; }
      else if (event.event === "run.finished") setRun((old) => old?.run_id === event.run_id ? null : old);
    }).then((unlisten) => { if (active) { stop = unlisten; onReady?.(true); } else unlisten(); }, () => {
      if (active) setError("执行事件监听失败，请重启应用后再执行。");
    });
    return () => { active = false; stop?.(); };
  }, [api, onReady]);
  async function cancel() {
    if (!run || !api.cancel || cancelling.current) return;
    cancelling.current = true; setPending(true);
    try {
      const accepted = await api.cancel(run.session_id, run.run_id);
      if (!accepted) setRun((old) => old?.run_id === run.run_id ? null : old);
    } catch { setError("无法发送取消请求，请重试。"); cancelling.current = false; setPending(false); }
  }
  return <>
    {run && executing && <div role="status" className="mb-3 rounded-lg bg-[var(--theme-chat-message-background)] p-3 text-sm">
      {pending ? "正在停止执行…" : "正在执行任务…"}
      {api.cancel && <button disabled={pending} className="ml-3 underline disabled:opacity-40" onClick={() => { void cancel(); }}>停止执行</button>}
    </div>}
    {error && <p role="alert">{error}</p>}
  </>;
}
