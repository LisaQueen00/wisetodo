import { useEffect, useRef, useState } from "react";
import { defaultTheme, MAX_THEME_BYTES, parseTheme, serializeTheme, type Theme } from "./model";
import type { useTheme } from "./useTheme";
import { invoke, isTauri } from "@tauri-apps/api/core";
import { ComponentEditor } from "./ComponentEditor";

const titles: Record<string, string> = { text: "文字", window: "窗口", todo: "Todo", chat: "Chat", settings: "设置", border: "边框", button: "按钮", input: "输入框", dropdown: "下拉菜单", status: "状态" };
export function ThemeSettings({ controller }: { controller: ReturnType<typeof useTheme> }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Theme>(defaultTheme);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const epoch = useRef(0);
  useEffect(() => {
    const node = dialog.current; if (!node) return;
    if (open) { if (node.showModal) node.showModal(); else node.setAttribute("open", ""); }
    else { if (node.close) node.close(); else node.removeAttribute("open"); }
  }, [open]);
  function edit(value: Theme) { setDraft(value); try { controller.preview(parseTheme(serializeTheme(value))); setError(""); } catch (cause) { setError(cause instanceof Error ? cause.message : "主题值无效。"); } }
  function close() { epoch.current++; controller.preview(null); setOpen(false); trigger.current?.focus(); }
  function checkedDraft() {
    if (dialog.current?.querySelector('[aria-invalid="true"]')) throw new Error("存在无效颜色，请修正后保存或导出。");
    return parseTheme(serializeTheme(draft));
  }
  async function exportTheme() {
    if (exporting) return;
    const ticket = epoch.current;
    setExporting(true); setError(""); setExportStatus("");
    try {
    const checked = checkedDraft();
    if (isTauri()) {
      const path = await invoke<string | null>("theme_export", { content: serializeTheme(checked) });
      if (ticket === epoch.current) setExportStatus(path ? `已导出到：${path}` : "已取消导出。");
      return;
    }
    const url = URL.createObjectURL(new Blob([serializeTheme(checked)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "wisetodo-theme.json";
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    setExportStatus("已请求浏览器下载，请检查下载列表。");
    } catch (cause) { if (ticket === epoch.current) setError(cause instanceof Error ? cause.message : typeof cause === "string" ? cause : "导出失败。"); }
    finally { setExporting(false); }
  }
  return <>
    <button ref={trigger} type="button" className="theme-launcher rounded-lg px-3 py-2 text-sm" onClick={() => {
      epoch.current++; setDraft(structuredClone(controller.active)); setError(controller.error); setExportStatus(""); setOpen(true);
    }}>主题设置</button>
    <dialog id="theme-editor" ref={dialog} aria-labelledby="theme-heading" className="theme-dialog" onCancel={(event) => { event.preventDefault(); close(); }}>
      {open && <>
        <h2 id="theme-heading">主题设置</h2>
        <p>修改立即预览，保存后留存；取消还原。配色难以辨认时可使用下方安全恢复入口。</p>
        <button id="theme-recovery" type="button" onClick={() => edit(structuredClone(defaultTheme))}>安全恢复默认配色</button>
        {draft.colors.text.primary.slice(0, 7).toLowerCase() === draft.colors.window.background.toLowerCase() && <p role="status">正文与窗口底色相同，可能无法阅读；建议调整后再保存。</p>}
        <label>已保存主题<select aria-label="已保存主题" value="" onChange={(event) => {
          const chosen = event.target.value === "default" ? defaultTheme : controller.themes[Number(event.target.value)];
          if (chosen) edit(structuredClone(chosen));
        }}><option value="" disabled>选择主题</option><option value="default">内置默认</option>{controller.themes.map((t, i) => <option key={t.name} value={i}>{t.name}</option>)}</select></label>
        <label>主题名称<input value={draft.name} maxLength={80} onChange={(e) => edit({ ...draft, name: e.target.value })} /></label>
        <button type="button" onClick={() => edit({ ...draft, name: `${draft.name.slice(0, 70)} 副本` })}>复制为自定义主题</button>
        <label>字体名称<input value={draft.font.family} maxLength={80} onChange={(e) => {
          const family = e.target.value;
          setDraft({ ...draft, font: { ...draft.font, family } });
          if (/^[\p{L}\p{N} _-]{1,80}$/u.test(family)) controller.preview({ ...draft, font: { ...draft.font, family } });
        }} /></label>
        <p>system 跟随系统；也可填写已安装字体名称。字体文件导入暂不支持，找不到时回退系统字体。</p>
        <label>基础字号<input type="number" min={12} max={20} value={draft.font.sizePx} onChange={(e) => {
          const sizePx = Number(e.target.value); if (Number.isInteger(sizePx) && sizePx >= 12 && sizePx <= 20) edit({ ...draft, font: { ...draft.font, sizePx } });
        }} /></label>
        <ComponentEditor theme={draft} onChange={edit} />
        {Object.entries(draft.colors).map(([group, colors]) => <details key={group}><summary>{titles[group]} · {group}</summary>
          {Object.entries(colors).map(([key, value]) => <ColorField key={key} label={`${group}.${key}`} value={value} onChange={(color) => {
            edit({ ...draft, colors: { ...draft.colors, [group]: { ...colors, [key]: color } } });
          }} />)}
        </details>)}
        <label>导入主题 JSON<input type="file" accept=".json,application/json" onChange={async (e) => {
          const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
          const ticket = ++epoch.current;
          try { if (file.size > MAX_THEME_BYTES) throw new Error("主题文件不能超过 64 KiB。");
            const value = parseTheme(await file.text()); if (ticket === epoch.current) edit(value);
          } catch (cause) { if (ticket === epoch.current) setError(cause instanceof Error ? cause.message : "导入失败。"); }
        }} /></label>
        <p>颜色用 #RRGGBB 或 #RRGGBBAA；窗口底色只用六位色值。背景不透明度独立，不随主题切换。</p>
        {error && <p role="alert">{error}</p>}
        {exportStatus && <p role="status">{exportStatus}</p>}
        <div className="theme-actions">
          <button onClick={() => { try { controller.save(checkedDraft()); setOpen(false); epoch.current++; trigger.current?.focus(); } catch (cause) { setError(cause instanceof Error ? cause.message : "保存失败。"); } }}>保存主题</button>
          <button onClick={close}>取消</button>
          <button onClick={() => edit(structuredClone(defaultTheme))}>恢复默认预览</button>
          <button disabled={exporting} onClick={exportTheme}>{exporting ? "正在导出…" : "导出 JSON"}</button>
        </div>
      </>}
    </dialog>
  </>;
}
function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const [text, setText] = useState(value);
  const [shown, setShown] = useState(value);
  if (shown !== value) { setShown(value); setText(value); }
  const valid = /^#[\da-f]{6}([\da-f]{2})?$/i.test(text) && (label !== "window.background" || text.length === 7);
  return <div className="theme-color-field">{label}<span className="theme-color-row"><input type="color" aria-label={`${label} 拾色`} value={value.slice(0, 7)} onChange={(e) => onChange(e.target.value + (value.length === 9 ? value.slice(7) : ""))} />
    <input aria-label={label} value={text} aria-invalid={!valid} onChange={(e) => { const next = e.target.value; setText(next);
      if (/^#[\da-f]{6}([\da-f]{2})?$/i.test(next) && (label !== "window.background" || next.length === 7)) onChange(next);
    }} /></span>{!valid && <small>请输入有效十六进制颜色，未应用该值。</small>}</div>;
}
