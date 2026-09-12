import { describe, expect, it } from "vitest";
import { defaultTheme, parseTheme, serializeTheme, themeVariables } from "./model";

describe("theme JSON", () => {
  it("round trips full defaults and fills omitted fields without mutating defaults", () => {
    expect(parseTheme(serializeTheme(defaultTheme))).toEqual(defaultTheme);
    const changed = parseTheme(JSON.stringify({ schemaVersion: 1, name: "阅读", colors: { dropdown: { text: "#AABBCC" } } }));
    expect(changed.colors.dropdown.text).toBe("#aabbcc");
    expect(changed.colors.todo).toEqual(defaultTheme.colors.todo);
    expect(defaultTheme.colors.dropdown.text).toBe("#f4eef9");
    expect(themeVariables(changed)["--theme-dropdown-text"]).toBe("#aabbcc");
  });
  it.each([
    { schemaVersion: 3, name: "x" }, { schemaVersion: 1, name: "" },
    { schemaVersion: 1, name: "x", colors: { dropdown: { missing: "#112233" } } },
    { schemaVersion: 1, name: "x", colors: { window: { background: "#11223300" } } },
    { schemaVersion: 1, name: "x", colors: { text: { primary: "url(https://example.com)" } } },
    { schemaVersion: 1, name: "x", font: { family: 'bad"; background:red' } },
    { schemaVersion: 1, name: "x", font: { sizePx: 200 } },
  ])("rejects invalid configuration %j", (value) => expect(() => parseTheme(JSON.stringify(value))).toThrow());
  it("rejects prototype/unknown keys and oversized JSON", () => {
    expect(() => parseTheme('{"schemaVersion":1,"name":"x","__proto__":{}}')).toThrow();
    expect(() => parseTheme(" ".repeat(65537))).toThrow();
  });
});
