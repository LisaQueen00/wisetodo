// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "../App";
import { defaultTheme, serializeTheme } from "./model";
import { ThemedSelect } from "./ThemedSelect";
import * as core from "@tauri-apps/api/core";

vi.mock("@tauri-apps/api/core", async (original) => ({ ...await original<typeof core>(), isTauri: vi.fn(() => false), invoke: vi.fn() }));

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function open() { fireEvent.click(screen.getByRole("button", { name: "主题设置" })); return screen.getByRole("dialog"); }
it("previews live, cancels, saves a named copy and restores it after remount", () => {
  const first = render(<App />);
  const dialog = open();
  fireEvent.click(within(dialog).getByText("文字 · text"));
  fireEvent.change(screen.getByLabelText("text.primary"), { target: { value: "#abcdef" } });
  expect(document.documentElement.style.getPropertyValue("--theme-text-primary")).toBe("#abcdef");
  fireEvent.click(within(dialog).getByText("取消"));
  expect(document.documentElement.style.getPropertyValue("--theme-text-primary")).toBe(defaultTheme.colors.text.primary);
  open(); fireEvent.click(screen.getByText("复制为自定义主题"));
  fireEvent.change(screen.getByLabelText("主题名称"), { target: { value: "我的主题" } });
  fireEvent.change(screen.getByLabelText("字体名称"), { target: { value: "Arial" } });
  fireEvent.click(screen.getByText("保存主题"));
  first.unmount(); render(<App />);
  expect(document.documentElement.style.getPropertyValue("--theme-font")).toContain('"Arial"');
  open(); expect(screen.getByLabelText("主题名称")).toHaveValue("我的主题");
});
it("does not overwrite defaults or save invalid color text", () => {
  render(<App />); open(); fireEvent.click(screen.getByText("文字 · text"));
  fireEvent.change(screen.getByLabelText("text.primary"), { target: { value: "bad" } });
  fireEvent.click(screen.getByText("保存主题")); expect(screen.getByRole("alert")).toHaveTextContent("无效颜色");
  fireEvent.change(screen.getByLabelText("text.primary"), { target: { value: "#aabbcc" } });
  fireEvent.click(screen.getByText("保存主题")); expect(screen.getByRole("alert")).toHaveTextContent("不可覆盖");
});
it("imports a partial theme into preview only and rejects invalid files", async () => {
  render(<App />); open();
  const input = screen.getByLabelText("导入主题 JSON");
  fireEvent.change(input, { target: { files: [{ size: 80, text: async () => '{"schemaVersion":1,"name":"导入主题","colors":{"dropdown":{"text":"#123456"}}}' }] } });
  await waitFor(() => expect(screen.getByLabelText("主题名称")).toHaveValue("导入主题"));
  expect(document.documentElement.style.getPropertyValue("--theme-dropdown-text")).toBe("#123456");
  expect(localStorage.getItem("wisetodo.themes.v1")).toBeNull();
  fireEvent.change(input, { target: { files: [{ size: 3, text: async () => "bad" }] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("JSON");
});
it("exports readable complete JSON without credentials or opacity preferences", () => {
  const blobs: Blob[] = [];
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: (blob: Blob) => { blobs.push(blob); return "blob:test"; }, revokeObjectURL: vi.fn() }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<App />); open(); fireEvent.click(screen.getByText("导出 JSON"));
  expect(blobs[0].size).toBe(new Blob([serializeTheme(defaultTheme)]).size);
});
it("keeps a failed save as preview and cancellation restores the old theme", () => {
  render(<App />); open(); fireEvent.click(screen.getByText("复制为自定义主题"));
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error(); });
  fireEvent.click(screen.getByText("保存主题")); expect(screen.getByRole("alert")).toHaveTextContent("保存失败");
  fireEvent.click(screen.getByText("取消")); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("waits for native writing, reports success, and prevents duplicate exports", async () => {
  render(<App />); open();
  vi.mocked(core.isTauri).mockReturnValue(true);
  let finish!: (value: string) => void;
  vi.mocked(core.invoke).mockReturnValue(new Promise<string>((resolve) => { finish = resolve; }));
  fireEvent.click(screen.getByText("导出 JSON"));
  expect(screen.getByText("正在导出…")).toBeDisabled();
  expect(core.invoke).toHaveBeenCalledWith("theme_export", { content: serializeTheme(defaultTheme) });
  expect(screen.queryByText(/已导出到/)).not.toBeInTheDocument();
  finish("D:\\themes\\我的主题.json");
  expect(await screen.findByText(/已导出到：D:/)).toBeInTheDocument();
});
it("distinguishes native cancellation from writing failure and allows retry", async () => {
  render(<App />); open();
  vi.mocked(core.isTauri).mockReturnValue(true);
  vi.mocked(core.invoke).mockResolvedValueOnce(null).mockRejectedValueOnce("主题文件写入失败。");
  fireEvent.click(screen.getByText("导出 JSON"));
  expect(await screen.findByText("已取消导出。")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText("导出 JSON"));
  expect(await screen.findByRole("alert")).toHaveTextContent("主题文件写入失败");
  expect(screen.getByText("导出 JSON")).toBeEnabled();
});
it("supports keyboard navigation, Escape and selection in themed dropdowns", () => {
  const change = vi.fn();
  render(<ThemedSelect aria-label="选项" value="a" onChange={change}><option value="a">Alpha</option><option value="b">Beta</option></ThemedSelect>);
  const control = screen.getByRole("combobox"); control.focus();
  fireEvent.keyDown(control, { key: "ArrowDown" }); expect(control).toHaveAttribute("aria-expanded", "true");
  fireEvent.keyDown(control, { key: "Enter" }); expect(change).toHaveBeenCalledWith({ target: { value: "b" } });
  fireEvent.click(control); fireEvent.keyDown(control, { key: "Escape" }); expect(control).toHaveAttribute("aria-expanded", "false");
});
it("previews component gradients and bold italic text and cancels the generated stylesheet", () => {
  render(<App />); open();
  fireEvent.click(screen.getByText("组件精细样式 · v2"));
  fireEvent.change(screen.getByLabelText("背景类型"), { target: { value: "linear" } });
  expect(document.querySelector("style[data-theme-components]")?.textContent).toContain("linear-gradient");
  fireEvent.change(screen.getByLabelText("组件"), { target: { value: "todoTitle" } });
  fireEvent.change(screen.getByLabelText("字重（700 为加粗）"), { target: { value: "700" } });
  fireEvent.change(screen.getByLabelText("斜体"), { target: { value: "italic" } });
  expect(document.querySelector("style[data-theme-components]")?.textContent).toContain("font-style:italic");
  expect(document.querySelector("style[data-theme-components]")?.textContent).toContain("font-weight:700");
  fireEvent.click(screen.getByText("取消"));
  expect(document.querySelector("style[data-theme-components]")?.textContent).toBe("");
});
it("updates base and decorative transparency independently at slider endpoints", () => {
  render(<App />);
  const slider = screen.getByLabelText(/背景不透明度/);
  const panel = document.querySelector(".app-panel") as HTMLElement;
  fireEvent.change(slider, { target: { value: "60" } });
  expect(panel.style.getPropertyValue("--panel-alpha")).toBe("0.6");
  expect(panel.style.getPropertyValue("--surface-alpha")).toBe("0");
  fireEvent.change(slider, { target: { value: "100" } });
  expect(panel.style.getPropertyValue("--panel-alpha")).toBe("1");
  expect(panel.style.getPropertyValue("--surface-alpha")).toBe("1");
});
