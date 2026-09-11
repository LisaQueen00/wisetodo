import { TodoWorkspace } from "./todos/TodoWorkspace";
import { useCallback, useRef, useState, type CSSProperties } from "react";
import { usePanelOpacity } from "./desktop/usePanelOpacity";
import type { LoadTodos, TodoMutations } from "./todos/types";
import { SessionPanel } from "./sessions/SessionPanel";
import type { SessionApi } from "./sessions/types";
import { SettingsPanel } from "./settings/SettingsPanel";
import type { SettingsApi } from "./settings/desktop";
import { DesktopControls } from "./desktop/DesktopControls";
import type { DesktopApi } from "./desktop/api";
import { ErrorNotice } from "./errors/ErrorNotice";

function App({ loadTodos, mutations, preview = false, sessionApi, settingsApi, desktopApi }: {
  loadTodos?: LoadTodos; mutations?: TodoMutations; preview?: boolean; sessionApi?: SessionApi;
  settingsApi?: SettingsApi;
  desktopApi?: DesktopApi;
}) {
  const [todoRevision, setTodoRevision] = useState(0);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatRunning, setChatRunning] = useState(false);
  const chatButton = useRef<HTMLButtonElement>(null);
  const { opacity, changeOpacity, saveFailed } = usePanelOpacity();
  const onCommitted = useCallback(() => setTodoRevision((value) => value + 1), []);
  return (
    <main style={{ "--panel-alpha": opacity / 100 } as CSSProperties} className="app-panel flex h-dvh min-h-[520px] flex-col overflow-hidden bg-[var(--surface-window)] text-[var(--text-primary)]">
      <ErrorNotice />
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 p-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">WiseTodo</h1>
            <p className="mt-1 text-xs text-white/45">一件一件，慢慢完成。</p>
          </div>
          <button ref={chatButton} aria-expanded={chatOpen} aria-controls="chat-overlay"
            className="rounded-lg bg-white/10 px-3 py-2 text-sm" onClick={() => setChatOpen((value) => !value)}>
            {chatOpen ? "收起 Chat" : "打开 Chat"}{chatRunning && <span role="status" className="ml-2 text-xs">执行中</span>}
          </button>
          <details className="w-full text-xs text-white/65"><summary className="cursor-pointer">桌面选项</summary>
            {desktopApi && <DesktopControls api={desktopApi} />}
            <label className="mt-3 block">背景不透明度：{opacity}%
              <input aria-label="背景不透明度" className="mt-2 block w-full" type="range" min={60} max={100} step={1}
                value={opacity} onChange={(event) => changeOpacity(Number(event.target.value))} />
            </label>
            <button className="mt-2 rounded bg-white/10 px-2 py-1" onClick={() => changeOpacity(100)}>恢复不透明背景</button>
            <p className="mt-2">仅背景淡化，仍可点击操作；桌面透视效果首版支持 Windows。</p>
            {saveFailed && <p role="alert">本次效果已应用，但未能保存，重启后可能恢复默认值。</p>}
          </details>
        </header>
      <div className="relative min-h-0 flex-1 overflow-hidden">
      <section aria-label="Todo 工作区" inert={chatOpen} aria-hidden={chatOpen}
        className={`absolute inset-0 flex min-h-0 min-w-0 flex-col ${chatOpen ? "invisible" : ""}`}>
        <div className="min-h-0 flex-1 overflow-y-auto p-3" tabIndex={0} aria-label="Todo 列表滚动区">
          {preview && <p className="mb-4 rounded-lg bg-white/5 p-3 text-xs text-white/60">示例数据预览 · 不会写入数据库</p>}
          {loadTodos ? <TodoWorkspace key={preview ? "preview" : "live"} loadTodos={loadTodos} mutations={mutations} refreshToken={todoRevision} /> : (
            <div role="status" className="rounded-2xl border border-dashed border-white/15 p-6">
              <p>请通过桌面应用查看 Todo</p>
              <p className="mt-2 text-sm text-white/50">浏览器无法连接本地数据库，请启动 WiseTodo 桌面应用。</p>
            </div>
          )}
        </div>
      </section>

      <aside id="chat-overlay" aria-label="Chat 工作区" inert={!chatOpen} aria-hidden={!chatOpen}
        data-open={chatOpen} className="chat-overlay absolute inset-0 flex min-h-0 min-w-0 flex-col p-3"
        onKeyDown={(event) => { if (event.key === "Escape" && !event.defaultPrevented && !event.nativeEvent.isComposing) {
          setChatOpen(false); chatButton.current?.focus();
        } }}>
        {settingsApi ? <SettingsPanel api={settingsApi} /> : <h2 className="mb-5 shrink-0 text-sm font-medium text-white/70">Chat</h2>}
        {sessionApi ? <SessionPanel api={sessionApi} visible={chatOpen} onRunningChange={setChatRunning} loadTodos={loadTodos} onCommitted={onCommitted} /> : <div className="min-h-0 flex-1 overflow-y-auto rounded-2xl border border-dashed border-white/15 p-6 text-sm leading-7 text-white/50">
          从一个想做的事情开始。<br />对话功能接入后，可以在这里讨论并创建任务。
        </div>}
        {!sessionApi && <textarea disabled aria-label="聊天输入（待接入）" placeholder="聊天功能待接入" rows={3}
          className="mt-4 w-full shrink-0 resize-none rounded-xl border border-white/10 bg-white/5 p-3 text-sm placeholder:text-white/30" />}
      </aside>
      </div>
    </main>
  );
}

export default App;
