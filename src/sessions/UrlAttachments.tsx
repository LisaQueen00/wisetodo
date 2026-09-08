import { useState } from "react";

function validateUrl(raw: string): string {
  const value = raw.trim();
  if (!/^https?:\/\//i.test(value) || /[\s\\]/u.test(value) || [...value].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127)) {
    throw new Error("请输入完整的 http:// 或 https:// 链接。");
  }
  let url: URL;
  try { url = new URL(value); }
  catch { throw new Error("链接格式无效，请检查网址和端口。"); }
  if (!url.hostname || url.username || url.password || value.slice(value.indexOf("://") + 3).split(/[/?#]/)[0].includes("@")) {
    throw new Error("链接不能包含用户名或密码。");
  }
  return value;
}

export function UrlAttachments({ urls, disabled, onChange }: {
  urls: readonly string[]; disabled: boolean; onChange: (urls: string[]) => void;
}) {
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  function add() {
    if (disabled) return;
    try {
      const value = validateUrl(input);
      if (urls.includes(value)) { setError("此链接已添加。"); return; }
      onChange([...urls, value]); setInput(""); setError("");
    } catch (failure) { setError(failure instanceof Error ? failure.message : "链接无效。"); }
  }
  return <div className="mb-2 space-y-2">
    <div className="flex gap-2">
      <input aria-label="URL 附件" placeholder="https://…" type="text" value={input} disabled={disabled}
        onChange={(event) => { setInput(event.target.value); setError(""); }}
        onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); if (!event.nativeEvent.isComposing && event.keyCode !== 229) add(); } }}
        className="min-w-0 flex-1 rounded-lg bg-white/5 p-2 text-sm" />
      <button type="button" disabled={disabled || !input.trim()} onClick={add}
        className="shrink-0 text-xs disabled:opacity-30">添加链接</button>
    </div>
    {error && <p role="alert" className="text-xs text-red-300">{error}</p>}
    {urls.length > 0 && <ul aria-label="待发送链接" className="max-h-32 space-y-1 overflow-y-auto">
      {urls.map((url) => <li key={url} className="flex items-start gap-2 rounded-lg bg-white/5 p-2 text-xs">
        <span className="min-w-0 flex-1 break-all">{url}</span>
        <button type="button" aria-label={`移除链接 ${url}`} disabled={disabled}
          onClick={() => onChange(urls.filter((value) => value !== url))} className="shrink-0 disabled:opacity-30">移除</button>
      </li>)}
    </ul>}
    <p className="text-xs text-white/40">只保存链接，不会自动访问网页。</p>
  </div>;
}
