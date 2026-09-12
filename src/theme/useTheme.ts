import { useLayoutEffect, useState } from "react";
import { defaultTheme, parseTheme, serializeTheme, themeVariables, type Theme } from "./model";
import { componentCss } from "./components";

const KEY = "wisetodo.themes.v1";
function load(): { themes: Theme[]; active: Theme; error: string } {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { themes: [], active: defaultTheme, error: "" };
    if (raw.length > 1500000) throw new Error();
    const data = JSON.parse(raw);
    if (!Array.isArray(data.themes) || data.themes.length > 20) throw new Error();
    const themes = data.themes.map((value: unknown) => parseTheme(JSON.stringify(value)));
    return { themes, active: themes.find((t: Theme) => t.name === data.active) ?? defaultTheme, error: "" };
  } catch { return { themes: [], active: defaultTheme, error: "主题记录无法读取，已使用默认主题；原记录未覆盖。" }; }
}
export function useTheme() {
  const [state, setState] = useState(load);
  const [preview, setPreview] = useState<Theme | null>(null);
  const active = preview ?? state.active;
  useLayoutEffect(() => {
    const root = document.documentElement;
    const vars = themeVariables(active);
    const previous = Object.keys(vars).map((key) => [key, root.style.getPropertyValue(key)]);
    const fontSize = root.style.fontSize;
    for (const [key, value] of Object.entries(vars)) root.style.setProperty(key, value);
    root.style.fontSize = `${active.font.sizePx}px`;
    const sheet = document.createElement("style"); sheet.dataset.themeComponents = "true";
    sheet.textContent = componentCss(active.palette, active.components); document.head.append(sheet);
    return () => { sheet.remove(); for (const [key, value] of previous) { if (value) root.style.setProperty(key, value); else root.style.removeProperty(key); } root.style.fontSize = fontSize; };
  }, [active]);
  function save(theme: Theme) {
    const checked = parseTheme(serializeTheme(theme));
    const isDefault = serializeTheme(checked) === serializeTheme(defaultTheme);
    if (!isDefault && checked.name === defaultTheme.name) throw new Error("内置默认主题不可覆盖，请更改名称后保存。");
    const themes = isDefault ? state.themes : [...state.themes.filter((t) => t.name !== checked.name), checked];
    if (themes.length > 20) throw new Error("最多保存 20 个自定义主题，请覆盖已有同名主题。");
    try { localStorage.setItem(KEY, JSON.stringify({ themes, active: checked.name })); }
    catch { throw new Error("保存失败，当前仅为预览；可导出 JSON 保留修改。"); }
    setState({ themes, active: checked, error: "" }); setPreview(null);
  }
  return { ...state, preview: setPreview, save };
}
