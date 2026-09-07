import { TodoWorkspace } from "./todos/TodoWorkspace";
import type { LoadTodos } from "./todos/types";

function App({ loadTodos, preview = false }: { loadTodos?: LoadTodos; preview?: boolean }) {
  return (
    <main className="grid h-dvh min-h-[520px] grid-cols-[minmax(0,3fr)_minmax(0,2fr)] overflow-hidden bg-[var(--surface-window)] text-[var(--text-primary)]">
      <section aria-label="Todo 工作区" className="flex min-h-0 min-w-0 flex-col border-r border-white/10">
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 p-5">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">WiseTodo</h1>
            <p className="mt-1 text-xs text-white/45">一件一件，慢慢完成。</p>
          </div>
          <span className="text-xs text-white/50">全部任务</span>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-5" tabIndex={0} aria-label="Todo 列表滚动区">
          {preview && <p className="mb-4 rounded-lg bg-white/5 p-3 text-xs text-white/60">示例数据预览 · 不会写入数据库</p>}
          {loadTodos ? <TodoWorkspace key={preview ? "preview" : "live"} loadTodos={loadTodos} /> : (
            <div role="status" className="rounded-2xl border border-dashed border-white/15 p-6">
              <p>请通过桌面应用查看 Todo</p>
              <p className="mt-2 text-sm text-white/50">浏览器无法连接本地数据库，请启动 WiseTodo 桌面应用。</p>
            </div>
          )}
        </div>
      </section>

      <aside aria-label="Chat 工作区" className="flex min-h-0 min-w-0 flex-col p-5">
        <h2 className="mb-5 shrink-0 text-sm font-medium text-white/70">Chat</h2>
        <div className="min-h-0 flex-1 overflow-y-auto rounded-2xl border border-dashed border-white/15 p-6 text-sm leading-7 text-white/50">
          从一个想做的事情开始。<br />对话功能接入后，可以在这里讨论并创建任务。
        </div>
        <textarea disabled aria-label="聊天输入（待接入）" placeholder="聊天功能待接入" rows={3}
          className="mt-4 w-full shrink-0 resize-none rounded-xl border border-white/10 bg-white/5 p-3 text-sm placeholder:text-white/30" />
      </aside>
    </main>
  );
}

export default App;
