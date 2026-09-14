import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { componentSelectors, supportedFields, supportedStates } from "./components";
import { MAX_THEME_BYTES, parseTheme } from "./model";

it("ships an importable template covering every component, supported state and field", () => {
  const text = readFileSync(new URL("../../docs/theme-v2.full.json", import.meta.url), "utf8");
  expect(new TextEncoder().encode(text).length).toBeLessThanOrEqual(MAX_THEME_BYTES);
  const theme = parseTheme(text);
  expect(Object.keys(theme.components)).toEqual(Object.keys(componentSelectors));
  for (const name of Object.keys(componentSelectors) as (keyof typeof componentSelectors)[]) {
    const states = theme.components[name]!;
    expect(Object.keys(states)).toEqual(supportedStates(name));
    for (const style of Object.values(states)) {
      expect(Object.keys(style)).toEqual(supportedFields(name));
      if (style.typography) expect(Object.keys(style.typography)).toHaveLength(7);
    }
  }
});
