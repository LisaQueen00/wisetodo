import { useEffect, useRef, useState } from "react";
import type { SettingsApi, SettingsUpdate, SettingsView } from "./desktop";
import { connectionMessages } from "./desktop";

const inputClass = "mt-1 w-full rounded-lg border border-white/15 bg-black/20 p-2 text-sm disabled:opacity-50";

export function SettingsPanel({ api }: { api: SettingsApi }) {
  const [saved, setSaved] = useState<SettingsView | null>(null);
  const [ready, setReady] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [key, setKey] = useState("");
  const [action, setAction] = useState<"keep" | "replace" | "clear">("keep");
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const saving = useRef(false);
  const generation = useRef(0);
  const trigger = useRef<HTMLButtonElement>(null);
  const unsaved = !saved || baseUrl.trim() !== saved.base_url || model.trim() !== saved.model || action !== "keep";

  useEffect(() => {
    const requests = generation;
    const ticket = ++generation.current;
    let active = true;
    api.get().then((value) => {
      if (!active || ticket !== generation.current) return;
      setSaved(value); setReady(true); setError("");
    }, () => {
      if (active && ticket === generation.current) setError("无法读取模型设置或系统凭据，请重试。不会自动清空已有配置。");
    });
    return () => { active = false; requests.current++; };
  }, [api, attempt]);

  function close() {
    if (saving.current) return;
    setKey(""); setOpen(false); setError(""); trigger.current?.focus();
  }

  async function testConnection() {
    if (saving.current || !saved || !api.test || (open && unsaved)) return;
    saving.current = true; setBusy(true); setTesting(true); setNotice(""); setError("");
    const ticket = generation.current;
    try {
      const status = await api.test();
      if (ticket === generation.current) {
        const message = Object.hasOwn(connectionMessages, status) ? connectionMessages[status] : "连接测试返回无效状态。";
        if (status === "ok") setNotice(message); else setError(message);
      }
    } catch {
      if (ticket === generation.current) setError("连接测试未完成，请检查服务后重试。未修改已保存配置。");
    } finally { saving.current = false; if (ticket === generation.current) { setBusy(false); setTesting(false); } }
  }

  async function save() {
    if (saving.current) return;
    const url = baseUrl.trim();
    const name = model.trim();
    try {
      const parsed = new URL(url);
      if (!/^https?:\/\//i.test(url) || /[\s\\]/.test(url) || [...url].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)
        || parsed.username || parsed.password || url.includes("@") || url.includes("?") || url.includes("#") || !name) throw new Error();
    } catch { setError("请填写有效的 HTTP(S) Base URL 和模型名，地址不能包含凭据、查询参数或片段。"); return; }
    if (saved?.has_api_key && saved.base_url !== url && action === "keep") {
      setError("更换地址时，请明确选择替换或清除已有密钥。"); return;
    }
    if (action === "replace" && (!key || /\s/.test(key))) {
      setError("请输入不含空白的新 API Key，或选择不使用密钥。"); return;
    }
    const payload: SettingsUpdate = action === "replace"
      ? { base_url: url, model: name, key_action: "replace", api_key: key }
      : { base_url: url, model: name, key_action: action };
    saving.current = true; setBusy(true); setError(""); setNotice("");
    const ticket = generation.current;
    try {
      const value = await api.save(payload);
      if (ticket !== generation.current) return;
      setSaved(value); setKey(""); setOpen(false);
      setNotice("设置已保存，下次启动自动读取。尚未测试模型连接。");
      trigger.current?.focus();
    } catch {
      if (ticket === generation.current) {
        setKey("");
        setError("保存未确认，请检查设置及系统凭据库。可重试；若超时，请取消后重新读取核对。替换密钥需重新输入。");
      }
    } finally { saving.current = false; if (ticket === generation.current) setBusy(false); }
  }

  return <section aria-label="模型连接设置" className="mb-3 shrink-0 text-xs">
    <div className="flex items-center justify-between gap-2">
      <h2 className="text-sm font-medium text-white/70">Chat</h2>
      <button ref={trigger} type="button" aria-expanded={open} aria-controls="model-settings-form"
        disabled={busy || !ready} className="rounded-lg border border-white/15 px-3 py-1.5 disabled:opacity-40"
        onClick={() => {
          if (open) { close(); return; }
          setBaseUrl(saved?.base_url ?? ""); setModel(saved?.model ?? "");
          setKey(""); setAction("keep"); setError(""); setNotice(""); setOpen(true);
        }}>Settings · 模型设置</button>
    </div>
    {!ready && !error && <p role="status" className="mt-2 text-white/50">读取模型设置…</p>}
    {ready && !saved && !open && <p className="mt-2 text-white/60">尚未配置模型，请打开 Settings；不影响手动管理 Todo 和查看历史。</p>}
    {ready && !open && <button type="button" disabled={busy} className="mt-2 text-white/50 underline" onClick={() => {
      setReady(false); setNotice(""); setError(""); setAttempt((value) => value + 1);
    }}>重新读取设置</button>}
    {error && <p role="alert" className="mt-2 text-rose-300">{error}</p>}
    {!ready && error && <button type="button" className="mt-2 underline" onClick={() => {
      setError(""); setAttempt((value) => value + 1);
    }}>重试读取设置</button>}
    {notice && <p role="status" className="mt-2 text-emerald-200">{notice}</p>}
    {open && <form id="model-settings-form" aria-label="编辑模型连接" className="mt-3 max-h-[45vh] overflow-y-auto rounded-xl border border-white/10 bg-white/5 p-3"
      onSubmit={(event) => { event.preventDefault(); void save(); }}
      onKeyDown={(event) => { if (event.key === "Escape" && !event.nativeEvent.isComposing) { event.preventDefault(); close(); } }}>
      <fieldset disabled={busy} className="space-y-3">
        <label className="block">Base URL<input autoFocus className={inputClass} value={baseUrl} onChange={(event) => { setBaseUrl(event.target.value); setNotice(""); setError(""); }} placeholder="http://localhost:8000/v1" autoComplete="off" spellCheck={false} /></label>
        <label className="block">模型名<input className={inputClass} value={model} onChange={(event) => { setModel(event.target.value); setNotice(""); setError(""); }} autoComplete="off" spellCheck={false} /></label>
        <label className="block">API Key 操作<select className={inputClass} value={action} onChange={(event) => { setAction(event.target.value as typeof action); setKey(""); setNotice(""); setError(""); }}>
          <option value="keep">{saved?.has_api_key ? "保留已保存的密钥" : "不使用密钥（本地服务）"}</option>
          <option value="replace">填写／替换密钥</option>
          <option value="clear">清除密钥，不使用鉴权</option>
        </select></label>
        {action === "replace" && <label className="block">新 API Key<input type="password" className={inputClass} value={key} onChange={(event) => setKey(event.target.value)} autoComplete="new-password" spellCheck={false} /></label>}
        <p className="text-white/50">全局连接设置，与会话无关。密钥保存到系统凭据库，不会显示原值。保存不发起模型请求。</p>
        {api.test && <div className="rounded-lg border border-white/10 p-2">
          <p className="text-white/50">仅测试已保存配置，发送一次“Reply OK.”，不发送聊天或附件，不自动重试；可能产生少量费用。</p>
          {unsaved && <p className="mt-1 text-amber-200">请先保存当前设置，再测试连接。</p>}
          <button type="button" disabled={busy || unsaved} className="mt-2 rounded-lg border border-white/15 px-3 py-2 disabled:opacity-40"
            onClick={() => { void testConnection(); }}>{testing ? "测试中…" : "测试连接"}</button>
        </div>}
        <div className="flex gap-3">
          <button type="submit" className="rounded-lg bg-purple-400/20 px-3 py-2">{busy && !testing ? "保存中…" : "保存设置"}</button>
          <button type="button" className="rounded-lg border border-white/15 px-3 py-2" onClick={close}>取消</button>
        </div>
      </fieldset>
    </form>}
  </section>;
}
