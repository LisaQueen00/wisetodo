// Generate a complete editable example from the application's actual catalogue.
import { readFileSync, writeFileSync } from "node:fs";
import { Buffer } from "node:buffer";
import { URL } from "node:url";
import { log } from "node:console";
import ts from "typescript";
import { componentSelectors, supportedFields, supportedStates } from "../src/theme/components.ts";

const modelUrl = new URL("../src/theme/model.ts", import.meta.url);
const source = readFileSync(modelUrl, "utf8").replace('"./components"', JSON.stringify(new URL("../src/theme/components.ts", import.meta.url).href));
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { defaultTheme, parseTheme, MAX_THEME_BYTES } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const theme = JSON.parse(JSON.stringify(defaultTheme));
theme.name = "WiseTodo 完整编辑模板";
theme.palette = {
  transparent: "#00000000", window: "#17131f", surface: "#211a2b", control: "#302739",
  hover: "#40334e", pressed: "#4d3c60", text: "#f4eef9", muted: "#b9afc5",
  disabled: "#81758e", border: "#655273", accent: "#a881d8", high: "#ef6a76",
  completed: "#b4c7be", error: "#fca5a5", track: "#ffffff14",
};
const ref = name => ({ ref: name });
const controls = new Set(["button", "primaryButton", "input", "chatInput", "dropdown", "dropdownMenu", "dropdownOption", "sessionButton", "todoTitleButton"]);
const surfaces = new Set(["todoCard", "chatPanel", "userMessage", "assistantMessage", "systemMessage", "sessionRow", "stage", "toolEvent", "modelSettings"]);
for (const name of Object.keys(componentSelectors)) {
  theme.components[name] = {};
  for (const state of supportedStates(name)) {
    const style = {};
    for (const field of supportedFields(name)) {
      if (field === "background") {
        let key = name === "window" ? "window" : controls.has(name) ? "control" : surfaces.has(name) ? "surface" : "transparent";
        if (controls.has(name) && ["hover", "focus"].includes(state)) key = "hover";
        if (controls.has(name) && ["active", "selected"].includes(state)) key = "pressed";
        if (["progressTrack", "scrollbarTrack"].includes(name)) key = "track";
        if (["progressFill", "scrollbarThumb"].includes(name)) key = "accent";
        style[field] = ref(key);
      } else if (field === "typography") {
        style[field] = { fontFamily: "system", fontSize: name === "appTitle" ? 20 : 14, fontWeight: ["appTitle", "todoTitle", "todoTitleButton"].includes(name) ? 600 : 400, fontStyle: "normal", lineHeight: 1.5, letterSpacing: 0, textDecoration: name === "completedTitle" ? "line-through" : "none" };
      } else {
        let key = field === "shadow" ? "transparent" : field === "border" ? "border" : field === "accent" ? "accent" : "text";
        if (field === "text") {
          if (["subtitle", "helpText", "placeholder", "todoNumber"].includes(name)) key = "muted";
          if (name === "priorityHigh") key = "high";
          if (name === "priorityNormal") key = "accent";
          if (name === "error") key = "error";
          if (name === "completedTitle" || state === "completed") key = "completed";
          if (state === "disabled") key = "disabled";
        }
        style[field] = ref(key);
      }
    }
    theme.components[name][state] = style;
  }
}
theme.components.window.default.background = { type: "linear", angle: 150, stops: [{ color: ref("window"), position: 0 }, { color: ref("surface"), position: 100 }] };
// One state per line keeps every field visible while staying below the 64 KiB import limit.
const header = JSON.stringify({ ...theme, components: undefined }, null, 2).slice(0, -2);
const entries = Object.entries(theme.components).map(([name, states]) =>
  `    "${name}": {\n${Object.entries(states).map(([state, style]) => `      "${state}": ${JSON.stringify(style)}`).join(",\n")}\n    }`);
const output = `${header},\n  "components": {\n${entries.join(",\n")}\n  }\n}\n`;
parseTheme(output);
if (Buffer.byteLength(output) > MAX_THEME_BYTES) throw new Error("Template exceeds import size limit");
writeFileSync(new URL("../docs/theme-v2.full.json", import.meta.url), output);
log(`Generated ${Object.keys(theme.components).length} components; ${Buffer.byteLength(output)} bytes`);
