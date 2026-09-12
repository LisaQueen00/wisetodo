import { Pin } from "lucide-react";
import { useEffect, useState } from "react";
import type { DesktopApi, DesktopStatus } from "./api";

export function DesktopControls({ api }: { api: DesktopApi }) {
  const [state, setState] = useState<DesktopStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api.status().then((value) => { if (active) { setState(value); setError(false); } },
      () => { if (active) setError(true); });
    return () => { active = false; };
  }, [api, attempt]);
  async function change(operation: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(false);
    try { await operation(); setState(await api.status()); }
    catch { setError(true); }
    finally { setBusy(false); }
  }
  return <div className="max-w-64 text-xs text-[var(--theme-text-secondary)]">
    <div className="flex items-center gap-3">
      <button aria-label="窗口置顶" aria-pressed={state?.pinned ?? false} disabled={!state || busy}
        className="flex items-center gap-1 rounded bg-[var(--theme-chat-message-background)] px-2 py-1 disabled:opacity-40"
        onClick={() => void change(() => api.pin(!state!.pinned))}>
        <Pin aria-hidden="true" className="size-3" />{state?.pinned ? "已置顶" : "置顶"}
      </button>
      <label><input type="checkbox" checked={state?.autostart ?? false} disabled={!state || state.autostart === null || busy}
        onChange={(event) => { const enabled = event.target.checked; void change(() => api.autostart(enabled)); }} /> 开机启动</label>
    </div>
    {state && <p className="mt-2">{state.tray_available ? "关闭窗口后在托盘运行；托盘菜单可退出。" : "托盘不可用，关闭窗口将退出应用。"}</p>}
    {state?.autostart === null && <p>当前无法读取系统开机启动设置。</p>}
    {state?.abnormal_exit && <div role="alert" className="mt-2 rounded border border-[var(--theme-status-warning)] p-2">
      <p>上次可能未正常退出。未自动恢复执行任务，是否重启应用？</p>
      <button disabled={busy} onClick={() => void change(api.restart)} className="mr-3 underline">确认重启</button>
      <button disabled={busy} onClick={() => void change(api.acknowledge)} className="underline">继续使用</button>
    </div>}
    {error && <p role="alert">桌面设置操作失败。<button disabled={busy} className="underline" onClick={() => setAttempt((n) => n + 1)}>重新读取</button></p>}
  </div>;
}
