/** The catalogue is shared by validation, editor, schema and CSS generation. */
export const componentSelectors = {
  global: ".app-panel", window: ".app-panel", header: ".app-panel > header",
  appTitle: ".app-panel > header h1", subtitle: ".app-panel > header p",
  todoList: '[aria-label="Todo 列表滚动区"]', todoCard: ".todo-card",
  todoTitle: ".todo-title", todoTitleButton: ".todo-card h3 button",
  completedTitle: '.todo-card[data-completed="true"] .todo-title',
  todoItem: ".todo-card ol > li", todoItemText: ".todo-card ol > li > div > span",
  todoNumber: ".todo-card ol > li::marker", priority: ".todo-priority",
  priorityHigh: '.todo-card[data-priority="1"] .todo-priority',
  priorityNormal: '.todo-card[data-priority="0"] .todo-priority',
  progressTrack: "progress::-webkit-progress-bar", progressFill: "progress::-webkit-progress-value",
  checkbox: 'input[type="checkbox"]', slider: 'input[type="range"]',
  chatPanel: ".chat-overlay", userMessage: '[data-message-role="user"]',
  assistantMessage: '[data-message-role="assistant"]', systemMessage: '[data-message-role="system"]',
  messageRole: '[data-message-role] > p:first-child', messageText: '[data-message-role] > p:nth-child(2)',
  attachment: '[aria-label="消息附件"] li, [aria-label="待发送文件"] li',
  sessionRow: '[aria-label="历史会话"] > li', sessionButton: '[aria-label="历史会话"] > li > button:first-child',
  composer: 'form[aria-label="发送消息"]', chatInput: 'form[aria-label="发送消息"] textarea',
  stage: "[data-stage]", toolEvent: '[data-stage="tool"]',
  modelSettings: "#model-settings-form", label: "label", helpText: "small",
  button: "button", primaryButton: 'button[type="submit"], form[aria-label="发送消息"] > button',
  input: 'input:not([type="checkbox"]):not([type="range"]):not([type="color"]), textarea',
  placeholder: "input::placeholder, textarea::placeholder",
  dropdown: '.themed-select > button', dropdownMenu: '.themed-select [role="listbox"]',
  dropdownOption: '.themed-select [role="option"]',
  error: '[role="alert"], [data-stage="error"]', notice: '[role="status"]',
  scrollbarThumb: ".app-panel *::-webkit-scrollbar-thumb", scrollbarTrack: ".app-panel *::-webkit-scrollbar-track",
} as const;
export type ComponentName = keyof typeof componentSelectors;
export const states = ["default", "hover", "active", "focus", "disabled", "selected", "completed", "dragging"] as const;
export type Color = string | { ref: string };
export type Paint = Color | { type: "linear" | "radial"; angle?: number; stops: { color: Color; position: number }[] };
export type Typography = { fontFamily?: string; fontSize?: number; fontWeight?: number; fontStyle?: "normal" | "italic"; lineHeight?: number; letterSpacing?: number; textDecoration?: "none" | "underline" | "line-through" };
export type Style = { background?: Paint; text?: Color; border?: Color; shadow?: Color; accent?: Color; typography?: Typography };
export type Components = Partial<Record<ComponentName, Partial<Record<typeof states[number], Style>>>>;
export function supportedStates(name: string): readonly typeof states[number][] {
  if (["todoNumber", "placeholder", "progressTrack", "progressFill", "scrollbarThumb", "scrollbarTrack", "global", "window"].includes(name)) return ["default"];
  const result: typeof states[number][] = ["default", "hover", "active", "focus"];
  if (["button", "primaryButton", "input", "chatInput", "checkbox", "slider", "dropdown", "dropdownOption", "sessionButton", "todoTitleButton"].includes(name)) result.push("disabled");
  if (["checkbox", "dropdownOption", "sessionButton"].includes(name)) result.push("selected");
  if (["todoCard", "todoItem", "todoItemText"].includes(name)) result.push("completed");
  return result;
}
export function supportedFields(name: string): (keyof Style)[] {
  if (["global", "placeholder", "todoNumber"].includes(name)) return ["text", "typography"];
  if (name.startsWith("progress") || name.startsWith("scrollbar")) return ["background"];
  if (["checkbox", "slider"].includes(name)) return ["accent"];
  return ["background", "text", "border", "shadow", "typography"];
}
const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
function fail(): never { throw new Error("组件主题字段或取值无效，请检查颜色引用、渐变、状态及文字样式。"); }
const only = (v: Record<string, unknown>, names: readonly string[]) => { if (Object.keys(v).some(k => !names.includes(k))) fail(); };
export function validateComponents(palette: unknown, components: unknown): void {
  if (!obj(palette) || !obj(components)) fail();
  for (const [key, value] of Object.entries(palette)) {
    if (!/^[a-zA-Z][a-zA-Z0-9_-]{0,63}$/.test(key) || typeof value !== "string" || !/^#[\da-f]{6}([\da-f]{2})?$/i.test(value)) fail();
  }
  const color = (v: unknown) => {
    if (typeof v === "string" && /^#[\da-f]{6}([\da-f]{2})?$/i.test(v)) return;
    if (obj(v) && Object.keys(v).length === 1 && typeof v.ref === "string" && Object.hasOwn(palette, v.ref)) return;
    fail();
  };
  only(components, Object.keys(componentSelectors));
  for (const [name, entries] of Object.entries(components)) {
    if (!obj(entries)) fail();
    only(entries, supportedStates(name));
    for (const style of Object.values(entries)) {
      if (!obj(style)) fail();
      only(style, supportedFields(name));
      for (const [key, v] of Object.entries(style)) {
        if (key === "typography") {
          if (!obj(v)) fail();
          only(v, ["fontFamily", "fontSize", "fontWeight", "fontStyle", "lineHeight", "letterSpacing", "textDecoration"]);
          for (const [field, n] of Object.entries(v)) {
            if (field === "fontFamily") { if (typeof n !== "string" || !/^[\p{L}\p{N} _-]{1,80}$/u.test(n)) fail(); }
            else if (field === "fontStyle") { if (!["normal", "italic"].includes(String(n))) fail(); }
            else if (field === "textDecoration") { if (!["none", "underline", "line-through"].includes(String(n))) fail(); }
            else { const bounds: Record<string, number[]> = { fontSize: [8, 48], fontWeight: [100, 900], lineHeight: [0.8, 3], letterSpacing: [-2, 10] }; const [min, max] = bounds[field]; if (typeof n !== "number" || !Number.isFinite(n) || n < min || n > max) fail(); }
          }
        } else if (key === "background" && obj(v) && "type" in v) {
          only(v, ["type", "angle", "stops"]);
          if (!["linear", "radial"].includes(String(v.type)) || !Array.isArray(v.stops) || v.stops.length < 2 || v.stops.length > 12) fail();
          if (v.angle !== undefined && (v.type !== "linear" || typeof v.angle !== "number" || !Number.isFinite(v.angle) || v.angle < 0 || v.angle > 360)) fail();
          let previous = -1;
          for (const stop of v.stops) { if (!obj(stop)) fail(); only(stop, ["color", "position"]); color(stop.color); if (typeof stop.position !== "number" || stop.position < previous || stop.position < 0 || stop.position > 100) fail(); previous = stop.position; }
        } else color(v);
      }
    }
  }
}
export function componentCss(palette: Record<string, string>, components: Components): string {
  const color = (v: Color) => typeof v === "string" ? v : palette[v.ref];
  // Controls stay readable. Decorative surfaces fade faster than the base window:
  // at the slider minimum they are transparent, avoiding a stack of opaque cards.
  const protectedBackgrounds = new Set(["button", "primaryButton", "input", "chatInput", "dropdown", "dropdownMenu", "dropdownOption", "modelSettings", "progressTrack", "progressFill", "scrollbarThumb", "scrollbarTrack"]);
  const paint = (v: Paint, name: string): string => {
    const factor = name === "window" ? "var(--panel-alpha, 0.85)" : "var(--surface-alpha, 0.625)";
    const resolve = (c: Color) => protectedBackgrounds.has(name) ? color(c) : `color-mix(in srgb, ${color(c)} calc(${factor} * 100%), transparent)`;
    return typeof v === "object" && "type" in v ? `${v.type}-gradient(${v.type === "linear" ? `${v.angle ?? 180}deg` : "ellipse at center"}, ${v.stops.map(s => `${resolve(s.color)} ${s.position}%`).join(", ")})` : resolve(v);
  };
  const suffix: Record<string, string> = { default: "", hover: ":hover", active: ":active", focus: ":focus-within", disabled: ":disabled", selected: ':is([aria-selected="true"], [aria-current="true"], [aria-pressed="true"], :checked)', completed: '[data-completed="true"]', dragging: '[aria-grabbed="true"]' };
  const order = [...new Set(["global", "window", "button", "input", "label", ...Object.keys(componentSelectors)])] as ComponentName[];
  return order.flatMap(name => states.flatMap(state => {
    const entries = components[name];
    const style = entries?.[state]; if (!style) return [];
    const rules: string[] = [];
    for (const [key, value] of Object.entries(style)) {
      if (key === "typography") {
        for (const [k, v] of Object.entries(value as Typography)) {
          const property = k.replace(/[A-Z]/g, c => `-${c.toLowerCase()}`);
          const val = k === "fontFamily" ? v === "system" ? "system-ui, sans-serif" : `"${v}", system-ui, sans-serif` : k === "fontSize" || k === "letterSpacing" ? `${v}px` : v;
          rules.push(`${property}:${val}!important`);
        }
      } else { const prop: Record<string, string> = { background: "background", text: "color", border: "border-color", shadow: "box-shadow", accent: "accent-color" }; rules.push(`${prop[key]}:${key === "background" ? paint(value as Paint, name) : key === "shadow" ? `0 4px 16px ${color(value as Color)}` : color(value as Color)}!important`); }
    }
    const selectors = componentSelectors[name as ComponentName].split(", ").map(s => {
      const pseudo = s.indexOf("::");
      const base = pseudo < 0 ? s : s.slice(0, pseudo);
      return `:root ${base.startsWith(".app-panel") ? "" : ".app-panel "}${base}:not(#theme-editor, #theme-editor *, .theme-launcher)${suffix[state]}${pseudo < 0 ? "" : s.slice(pseudo)}`;
    });
    // Global typography/text explicitly reaches utility-styled descendants; component rules follow it.
    if (name === "global" && state === "default") selectors.push(":root .app-panel *:not(#theme-editor, #theme-editor *, .theme-launcher)");
    return `${selectors.join(",")}{${rules.join(";")}}`;
  })).join("\n");
}
