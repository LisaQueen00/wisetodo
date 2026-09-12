import { validateComponents, type Components } from "./components";
/** Human-editable, data-only themes. No CSS, URLs, scripts or font downloads. */
export const defaultTheme = {
  schemaVersion: 2,
  palette: {} as Record<string, string>,
  components: {} as Components,
  name: "WiseTodo 默认",
  font: { family: "system", sizePx: 16 },
  colors: {
    text: { primary: "#f4eef9", secondary: "#ffffff99", muted: "#ffffff73" },
    window: { background: "#17131f", header: "#00000000" },
    todo: { background: "#211a2b29", border: "#a881d859", priorityHigh: "#ef6a76", priorityNormal: "#a881d8", completedText: "#b4c7be", completedBackground: "#1d232433" },
    chat: { background: "#00000000", messageBackground: "#ffffff0d" },
    settings: { background: "#ffffff0d" },
    border: { normal: "#ffffff26" },
    button: { background: "#ffffff1a", text: "#f4eef9", hoverBackground: "#ffffff26", primaryBackground: "#c084fc33", primaryText: "#f4eef9", disabledText: "#ffffff66" },
    input: { background: "#ffffff0d", text: "#f4eef9", placeholder: "#ffffff4d", border: "#ffffff26" },
    dropdown: { background: "#211a2b", text: "#f4eef9", itemHoverBackground: "#ffffff26", itemSelectedBackground: "#a881d833", itemSelectedText: "#f4eef9" },
    status: { error: "#fca5a5", success: "#a7f3d0", warning: "#fde68a", focus: "#a881d8", highlight: "#b491fa", progressTrack: "#ffffff14" },
  },
};
export type Theme = typeof defaultTheme;
export const MAX_THEME_BYTES = 65536;
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
function keys(value: Record<string, unknown>, allowed: string[]) {
  if (Object.keys(value).some((key) => !allowed.includes(key))) throw new Error("主题包含未知字段，请检查字段拼写。");
}
export function parseTheme(text: string): Theme {
  if (new TextEncoder().encode(text).length > MAX_THEME_BYTES) throw new Error("主题文件不能超过 64 KiB。");
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new Error("不是有效 JSON。"); }
  if (!record(value) || ![1, 2].includes(Number(value.schemaVersion)) || typeof value.schemaVersion !== "number") throw new Error("仅支持 schemaVersion: 1 或 2 的主题。");
  keys(value, value.schemaVersion === 1 ? ["schemaVersion", "name", "font", "colors"] : ["schemaVersion", "name", "font", "colors", "palette", "components"]);
  const result = structuredClone(defaultTheme);
  if (typeof value.name !== "string" || !value.name.trim() || value.name.length > 80) throw new Error("主题名称需为 1–80 个字符。");
  result.name = value.name.trim();
  if (value.font !== undefined) {
    if (!record(value.font)) throw new Error("font 必须是对象。");
    keys(value.font, ["family", "sizePx"]);
    const family = value.font.family ?? result.font.family;
    const size = value.font.sizePx ?? result.font.sizePx;
    if (typeof family !== "string" || !/^[\p{L}\p{N} _-]{1,80}$/u.test(family)) throw new Error("字体请填写 system 或本机字体名称，不支持 URL/CSS。");
    if (typeof size !== "number" || !Number.isInteger(size) || size < 12 || size > 20) throw new Error("基础字号需为 12–20 的整数。");
    result.font = { family, sizePx: size };
  }
  if (value.colors !== undefined) {
    if (!record(value.colors)) throw new Error("colors 必须是对象。");
    keys(value.colors, Object.keys(result.colors));
    for (const [group, colors] of Object.entries(value.colors)) {
      if (!record(colors)) throw new Error(`colors.${group} 必须是对象。`);
      const target = result.colors[group as keyof Theme["colors"]] as Record<string, string>;
      keys(colors, Object.keys(target));
      for (const [key, color] of Object.entries(colors)) {
        if (typeof color !== "string" || !/^#[\da-f]{6}([\da-f]{2})?$/i.test(color)) throw new Error(`${group}.${key} 请使用 #RRGGBB 或 #RRGGBBAA。`);
        if (group === "window" && key === "background" && color.length !== 7) throw new Error("窗口底色请用六位颜色；不透明度由桌面选项控制。");
        target[key] = color.toLowerCase();
      }
    }
  }
  validateComponents(value.palette ?? {}, value.components ?? {});
  result.palette = (value.palette ?? {}) as Record<string, string>;
  result.components = (value.components ?? {}) as Components;
  return result;
}
export const serializeTheme = (theme: Theme) => JSON.stringify(theme, null, 2) + "\n";
const kebab = (key: string) => key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
export function themeVariables(theme: Theme): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const [group, values] of Object.entries(theme.colors)) {
    for (const [key, value] of Object.entries(values)) vars[`--theme-${group}-${kebab(key)}`] = value;
  }
  vars["--theme-font"] = theme.font.family === "system" ? "system-ui, sans-serif" : `"${theme.font.family}", system-ui, sans-serif`;
  return vars;
}
