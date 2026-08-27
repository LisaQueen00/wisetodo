function App() {
  return (
    <main className="grid min-h-screen grid-cols-[3fr_2fr] bg-[var(--surface-window)] text-[var(--text-primary)]">
      <section className="border-r border-white/10 p-5">
        <header className="mb-5 flex items-center justify-between">
          <h1 className="text-xl font-semibold tracking-tight">WiseTodo</h1>
          <button className="rounded-lg bg-white/10 px-3 py-1.5 text-sm hover:bg-white/15">
            新增 Todo
          </button>
        </header>
        <div className="rounded-xl border border-dashed border-white/15 p-6 text-sm text-white/55">
          Todo 列表将在这里显示。
        </div>
      </section>

      <aside className="flex min-w-0 flex-col p-5">
        <h2 className="mb-5 text-sm font-medium text-white/70">Chat</h2>
        <div className="flex-1 rounded-xl border border-dashed border-white/15 p-6 text-sm text-white/55">
          创建一个 Session，告诉 WiseTodo 你想完成什么。
        </div>
        <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white/45">
          输入文字、URL，或将文件拖到这里
        </div>
      </aside>
    </main>
  );
}

export default App;
