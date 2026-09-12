import { useState } from "react";
import { componentSelectors, states, supportedStates, supportedFields, type ComponentName, type Style, type Typography } from "./components";
import { parseTheme, serializeTheme, type Theme } from "./model";

export function ComponentEditor({ theme, onChange }: { theme: Theme; onChange: (theme: Theme) => void }) {
  const [component, setComponent] = useState<ComponentName>("todoCard");
  const [state, setState] = useState<typeof states[number]>("default");
  const [error, setError] = useState("");
  const [json, setJson] = useState("");
  const style = theme.components[component]?.[state] ?? {};
  function edit(next: Style) {
    const candidate = { ...theme, components: { ...theme.components, [component]: { ...theme.components[component], [state]: next } } };
    try { onChange(parseTheme(serializeTheme(candidate))); setError(""); } catch (e) { setError(String(e)); }
  }
  function typography(key: keyof Typography, value: string | number) { edit({ ...style, typography: { ...style.typography, [key]: value } }); }
  return <details><summary>组件精细样式 · v2</summary>
    <p>未配置继承现有样式。先选组件与状态，再修改；纯色支持 #RRGGBBAA。全局 global 建议仅设置文字。渐变与引用也可通过下方 JSON 编辑。</p>
    <label>组件<select value={component} onChange={e => { setComponent(e.target.value as ComponentName); setState("default"); setError(""); }}>{Object.keys(componentSelectors).map(key => <option key={key}>{key}</option>)}</select></label>
    <label>状态<select value={state} onChange={e => setState(e.target.value as typeof state)}>{supportedStates(component).map(key => <option key={key}>{key}</option>)}</select></label>
    <p>映射：<code>{componentSelectors[component]}</code></p>
    {(["text", "border", "shadow", "accent"] as const).filter(key => supportedFields(component).includes(key)).map(key => <label key={key}>{key}<input placeholder="留空继承；#RRGGBB 或 #RRGGBBAA" key={`${component}-${state}-${key}-${JSON.stringify(style[key])}`} defaultValue={typeof style[key] === "string" ? style[key] : ""} onBlur={e => { const next = { ...style }; if (!e.target.value) delete next[key]; else next[key] = e.target.value; edit(next); }} /></label>)}
    {supportedFields(component).includes("background") && <label>背景类型<select value={typeof style.background === "object" && "type" in style.background ? style.background.type : style.background ? "solid" : "inherit"} onChange={e => {
      const next = { ...style }; if (e.target.value === "inherit") delete next.background;
      else next.background = e.target.value === "solid" ? "#211a2b" : { type: e.target.value as "linear" | "radial", stops: [{ color: "#292338", position: 0 }, { color: "#171722", position: 100 }] };
      edit(next);
    }}><option value="inherit">继承</option><option value="solid">纯色</option><option value="linear">线性渐变</option><option value="radial">径向渐变</option></select></label>}
    {typeof style.background === "string" && <label>背景色<input key={`${component}-${state}-${style.background}`} defaultValue={style.background} onBlur={e => edit({ ...style, background: e.target.value })} /></label>}
    {typeof style.background === "object" && "type" in style.background && (() => {
      const bg = style.background;
      return <div>{bg.type === "linear" && <label>渐变角度<input type="number" min="0" max="360" value={bg.angle ?? 180} onChange={e => edit({ ...style, background: { ...bg, angle: Number(e.target.value) } })} /></label>}
        {bg.stops.map((stop, index) => <div key={index}><label>色标 {index + 1}<input defaultValue={typeof stop.color === "string" ? stop.color : ""} key={JSON.stringify(stop.color)} onBlur={e => edit({ ...style, background: { ...bg, stops: bg.stops.map((s, i) => i === index ? { ...s, color: e.target.value } : s) } })} /></label>
          <label>位置 %<input type="number" min="0" max="100" value={stop.position} onChange={e => edit({ ...style, background: { ...bg, stops: bg.stops.map((s, i) => i === index ? { ...s, position: Number(e.target.value) } : s) } })} /></label>
          <button disabled={bg.stops.length <= 2} onClick={() => edit({ ...style, background: { ...bg, stops: bg.stops.filter((_, i) => i !== index) } })}>移除此色标</button></div>)}
        <button disabled={bg.stops.length >= 12} onClick={() => edit({ ...style, background: { ...bg, stops: [...bg.stops, { color: "#ffffff", position: 100 }] } })}>添加色标</button></div>;
    })()}
    {supportedFields(component).includes("typography") && <div><label>组件字体<input key={`${component}-${state}-font`} defaultValue={style.typography?.fontFamily ?? ""} placeholder="system 或已安装字体" onBlur={e => { if (e.target.value) typography("fontFamily", e.target.value); }} /></label>
    {([ ["fontSize", "字号 px", 8, 48, 1], ["fontWeight", "字重（700 为加粗）", 100, 900, 100], ["lineHeight", "行高倍率", 0.8, 3, 0.1], ["letterSpacing", "字间距 px", -2, 10, 0.1] ] as const).map(([key, title, min, max, step]) => <label key={key}>{title}<input type="number" min={min} max={max} step={step} value={style.typography?.[key] ?? ""} onChange={e => { const next = { ...style.typography }; if (e.target.value === "") delete next[key]; else next[key] = Number(e.target.value); edit({ ...style, typography: next }); }} /></label>)}
    <label>斜体<select value={style.typography?.fontStyle ?? ""} onChange={e => typography("fontStyle", e.target.value)}><option value="" disabled>继承</option><option value="normal">正常</option><option value="italic">斜体</option></select></label>
    <label>装饰<select value={style.typography?.textDecoration ?? ""} onChange={e => typography("textDecoration", e.target.value)}><option value="" disabled>继承</option><option value="none">无</option><option value="underline">下划线</option><option value="line-through">删除线</option></select></label>
    </div>}<button onClick={() => edit({})}>重置当前组件状态</button>
    <details><summary>高级 JSON：palette 与 components</summary><button onClick={() => setJson(JSON.stringify({ palette: theme.palette, components: theme.components }, null, 2))}>载入当前配置</button>
      <textarea aria-label="组件 JSON" rows={12} value={json} onChange={e => setJson(e.target.value)} />
      <button onClick={() => { try { const value = JSON.parse(json); if (!value || Object.keys(value).some(k => !["palette", "components"].includes(k))) throw new Error("仅填写 palette 与 components"); onChange(parseTheme(serializeTheme({ ...theme, palette: value.palette ?? {}, components: value.components ?? {} }))); setError(""); } catch (e) { setError(String(e)); } }}>校验并预览组件 JSON</button></details>
    {error && <p role="alert" aria-invalid="true">{error}</p>}
  </details>;
}
