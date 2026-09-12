import { expect, it } from "vitest";
import { componentCss, componentSelectors, supportedFields, supportedStates } from "./components";
import { parseTheme } from "./model";
const theme = (components: unknown, palette = {}) => parseTheme(JSON.stringify({ schemaVersion: 2, name: "test", palette, components }));
it("migrates v1 and supports gradients, palette references and typography", () => {
  expect(parseTheme('{"schemaVersion":1,"name":"old"}').schemaVersion).toBe(2);
  const t = theme({ todoCard: { default: { background: { type: "linear", angle: 135, stops: [{ color: { ref: "a" }, position: 0 }, { color: "#12345680", position: 100 }] } } }, todoTitle: { default: { typography: { fontWeight: 700, fontStyle: "italic", lineHeight: 1.6, letterSpacing: 0.5 } } } }, { a: "#abcdef" });
  const css = componentCss(t.palette, t.components);
  expect(css).toContain("linear-gradient(135deg, color-mix(in srgb, #abcdef");
  expect(css).toContain("var(--surface-alpha, 0.625)");
  expect(css).toContain("#12345680");
  expect(css).toContain("font-weight:700!important"); expect(css).toContain("font-style:italic!important");
  expect(css).toContain("#theme-editor *");
});
it("fades decorative radial backgrounds in every state without fading text or controls", () => {
  const t = theme({ chatPanel: { default: { background: { type: "radial", stops: [{ color: "#ffffff", position: 0 }, { color: "#aabbcc80", position: 100 }] }, text: "#123456" }, hover: { background: "#ffffff" } }, dropdownMenu: { default: { background: "#ffffff" } }, modelSettings: { default: { background: "#ffffff" } } });
  const css = componentCss(t.palette, t.components);
  expect(css).toContain("radial-gradient(ellipse at center, color-mix");
  expect(css).toContain("color:#123456!important");
  expect(css).not.toContain("opacity:");
  expect(css).toContain("background:#ffffff!important");
  expect(css.split("var(--surface-alpha, 0.625)")).toHaveLength(4);
});
it("maps every published component/state and field to a CSS rule", () => {
  for (const name of Object.keys(componentSelectors)) for (const state of supportedStates(name)) {
    const style = Object.fromEntries(supportedFields(name).map(f => [f, f === "typography" ? { fontSize: 19 } : "#123456"]));
    const t = theme({ [name]: { [state]: style } });
    const css = componentCss(t.palette, t.components);
    expect(css).toContain("!important"); expect(css).toContain(name === "global" ? ".app-panel" : componentSelectors[name as keyof typeof componentSelectors].split(", ")[0].split("::")[0]);
  }
});
it.each([
  { todoCard: { default: { text: { ref: "missing" } } } },
  { todoCard: { default: { background: "url(https://example.com)" } } },
  { todoCard: { default: { typography: { fontSize: 1000 } } } },
  { todoCard: { default: { typography: { fontFamily: 'bad";color:red' } } } },
  { todoCard: { default: { background: { type: "linear", stops: [{ color: "#ffffff", position: 90 }, { color: "#000000", position: 20 }] } } } },
  { checkbox: { default: { background: "#ffffff" } } },
  { todoTitle: { disabled: { text: "#ffffff" } } },
])("rejects unsafe and unmapped settings", components => expect(() => theme(components)).toThrow());
it("uses deterministic global-to-component ordering and preserves window alpha", () => {
  const t = theme({ todoTitle: { default: { text: "#123456" } }, global: { default: { text: "#ffffff" } }, window: { default: { background: "#123456" } } });
  const css = componentCss(t.palette, t.components);
  expect(css.indexOf(".todo-title")).toBeGreaterThan(css.indexOf(".app-panel"));
  expect(css).toContain("var(--panel-alpha, 0.85)");
});
