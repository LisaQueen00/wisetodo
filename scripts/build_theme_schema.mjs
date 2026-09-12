// Generated documentation artifact; source of component names/fields is the runtime catalogue.
import { writeFileSync } from "node:fs";
import { URL } from "node:url";
import { componentSelectors, supportedFields, supportedStates } from "../src/theme/components.ts";
const object = (properties, required = []) => ({ type: "object", additionalProperties: false, properties, required });
const hex = { type: "string", pattern: "^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$" };
const color = { oneOf: [hex, object({ ref: { type: "string", description: "引用 palette 中已定义的名称" } }, ["ref"])] };
const number = (minimum, maximum) => ({ type: "number", minimum, maximum });
const typography = object({ fontFamily: { type: "string", minLength: 1, maxLength: 80, description: "system 或本机已安装字体；不支持 CSS/URL" }, fontSize: number(8, 48), fontWeight: number(100, 900), fontStyle: { enum: ["normal", "italic"] }, lineHeight: number(0.8, 3), letterSpacing: number(-2, 10), textDecoration: { enum: ["none", "underline", "line-through"] } });
const stops = { type: "array", minItems: 2, maxItems: 12, description: "按 position 升序；运行时检查排序与引用", items: object({ color, position: number(0, 100) }, ["color", "position"]) };
const background = { oneOf: [color, object({ type: { const: "linear" }, angle: number(0, 360), stops }, ["type", "stops"]), object({ type: { const: "radial" }, stops }, ["type", "stops"])] };
const fields = { background, text: color, border: color, shadow: { ...color, description: "阴影颜色；几何固定为 0 4px 16px" }, accent: color, typography };
const styleDefinitions = {};
const components = object(Object.fromEntries(Object.entries(componentSelectors).map(([name, selector]) => {
  const key = supportedFields(name).join("_");
  styleDefinitions[key] = object(Object.fromEntries(supportedFields(name).map(field => [field, { $ref: `#/$defs/${field}` }])));
  return [name, { ...object(Object.fromEntries(supportedStates(name).map(state => [state, { $ref: `#/$defs/${key}` }]))), description: `样式映射：${selector}；缺省继承现有样式` }];
})));
const groups = { text: "primary secondary muted", window: "background header", todo: "background border priorityHigh priorityNormal completedText completedBackground", chat: "background messageBackground", settings: "background", border: "normal", button: "background text hoverBackground primaryBackground primaryText disabledText", input: "background text placeholder border", dropdown: "background text itemHoverBackground itemSelectedBackground itemSelectedText", status: "error success warning focus highlight progressTrack" };
const colors = object(Object.fromEntries(Object.entries(groups).map(([name, keys]) => [name, object(Object.fromEntries(keys.split(" ").map(key => [key, name === "window" && key === "background" ? { type: "string", pattern: "^#[0-9a-fA-F]{6}$" } : hex])))])));
const schema = { $schema: "https://json-schema.org/draft/2020-12/schema", title: "WiseTodo Theme v2", description: "组件颜色、渐变与文字样式；64 KiB 上限，引用与渐变排序由应用二次校验。", ...object({ schemaVersion: { const: 2 }, name: { type: "string", minLength: 1, maxLength: 80 }, font: object({ family: { type: "string", minLength: 1, maxLength: 80 }, sizePx: { type: "integer", minimum: 12, maximum: 20 } }), colors, palette: { type: "object", propertyNames: { pattern: "^[a-zA-Z][a-zA-Z0-9_-]{0,63}$" }, additionalProperties: hex }, components }, ["schemaVersion", "name"]) };
schema.$defs = { ...fields, ...Object.fromEntries(Object.entries(styleDefinitions).map(([key, value]) => [`style_${key}`, value])) };
// Prefix style references to avoid collisions with a single-field definition.
for (const component of Object.values(components.properties)) for (const state of Object.values(component.properties)) state.$ref = state.$ref.replace("#/$defs/", "#/$defs/style_");
writeFileSync(new URL("../docs/theme-v2.schema.json", import.meta.url), JSON.stringify(schema, null, 2) + "\n");
