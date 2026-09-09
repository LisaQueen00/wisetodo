// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SettingsPanel } from "./SettingsPanel";
import type { SettingsApi, SettingsView } from "./desktop";

afterEach(cleanup);
const stored: SettingsView = { base_url: "http://localhost:8000/v1", model: "local", has_api_key: true };
function api(value: SettingsView | null = stored): SettingsApi {
  return { get: vi.fn().mockResolvedValue(value), save: vi.fn().mockResolvedValue(stored) };
}
async function open() {
  const button = screen.getByRole("button", { name: "Settings · 模型设置" });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
}

describe("model settings panel", () => {
  it("shows connection testing only inside settings, including after saving", async () => {
    const service = api();
    service.test = vi.fn();
    render(<SettingsPanel api={service} />);
    await waitFor(() => expect((screen.getByRole("button", { name: "Settings · 模型设置" }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByRole("button", { name: /测试.*连接/ })).toBeNull();
    await open();
    expect(screen.getByRole("button", { name: "测试连接" })).toBeTruthy();
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByText(/设置已保存/);
    expect(screen.queryByRole("button", { name: /测试.*连接/ })).toBeNull();
    await open();
    expect(screen.getByRole("button", { name: "测试连接" })).toBeTruthy();
    expect(service.test).not.toHaveBeenCalled();
  });
  it("offers testing inside settings without saving and prevents repeated clicks", async () => {
    const service = api();
    let finish!: (value: string) => void;
    service.test = vi.fn(() => new Promise<string>((resolve) => { finish = resolve; }));
    render(<SettingsPanel api={service} />);
    await open();
    expect(service.test).not.toHaveBeenCalled();
    const button = screen.getByRole("button", { name: "测试连接" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(service.test).toHaveBeenCalledTimes(1);
    expect(screen.getByText("测试中…")).toBeTruthy();
    expect(screen.queryByText("保存中…")).toBeNull();
    await act(async () => finish("ok"));
    expect(screen.getByRole("form")).toBeTruthy();
    expect(screen.getByText(/基本连接测试通过/)).toBeTruthy();
    expect(service.save).not.toHaveBeenCalled();
  });
  it.each(["Base URL", "模型名", "API Key 操作"])("requires saving edits to %s before testing", async (field) => {
    const service = api();
    service.test = vi.fn().mockResolvedValue("ok");
    render(<SettingsPanel api={service} />);
    await open();
    fireEvent.change(screen.getByLabelText(field), { target: { value: field === "API Key 操作" ? "clear" : "changed" } });
    const button = screen.getByRole("button", { name: "测试连接" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByText(/请先保存当前设置/)).toBeTruthy();
    fireEvent.click(button);
    expect(service.test).not.toHaveBeenCalled();
  });
  it("keeps the first-use test disabled and saving does not automatically test", async () => {
    const service = api(null);
    service.test = vi.fn();
    render(<SettingsPanel api={service} />);
    await open();
    expect((screen.getByRole("button", { name: "测试连接" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: stored.base_url } });
    fireEvent.change(screen.getByLabelText("模型名"), { target: { value: stored.model } });
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByText(/设置已保存/);
    expect(service.test).not.toHaveBeenCalled();
  });
  it("shows test failure inside the open form without automatic retry", async () => {
    const service = api();
    service.test = vi.fn().mockResolvedValue("authentication");
    render(<SettingsPanel api={service} />);
    await open();
    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));
    await screen.findByText(/鉴权失败/);
    expect(service.test).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("form")).toBeTruthy();
  });
  it("tests only on explicit click and warns about cost", async () => {
    const service = api();
    service.test = vi.fn().mockResolvedValue("ok");
    render(<SettingsPanel api={service} />);
    await open();
    const button = screen.getByRole("button", { name: "测试连接" });
    expect(service.test).not.toHaveBeenCalled();
    expect(screen.getByText(/可能产生少量费用/)).toBeTruthy();
    fireEvent.click(button);
    await screen.findByText(/基本连接测试通过/);
    expect(service.test).toHaveBeenCalledTimes(1);
    expect(service.save).not.toHaveBeenCalled();
  });
  it("prevents duplicate saves and cancellation while saving", async () => {
    const service = api();
    let finish!: (value: SettingsView) => void;
    vi.mocked(service.save).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<SettingsPanel api={service} />);
    await open();
    const form = screen.getByRole("form");
    fireEvent.submit(form);
    fireEvent.submit(form);
    fireEvent.keyDown(screen.getByLabelText("模型名"), { key: "Escape" });
    expect(screen.getByRole("form")).toBe(form);
    expect(service.save).toHaveBeenCalledTimes(1);
    expect((screen.getByLabelText("模型名").closest("fieldset") as HTMLFieldSetElement).disabled).toBe(true);
    await act(async () => finish(stored));
    expect(screen.queryByRole("form")).toBeNull();
  });
  it("guides first use without automatically opening a form", async () => {
    const service = api(null);
    render(<SettingsPanel api={service} />);
    await screen.findByText(/尚未配置模型/);
    expect(screen.queryByRole("form")).toBeNull();
    await open();
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: stored.base_url } });
    fireEvent.change(screen.getByLabelText("模型名"), { target: { value: stored.model } });
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByText(/设置已保存/);
    expect(service.save).toHaveBeenCalledWith({ base_url: stored.base_url, model: stored.model, key_action: "keep" });
  });
  it("restores existing settings and cancel discards draft and key", async () => {
    const service = api();
    render(<SettingsPanel api={service} />);
    await open();
    expect((screen.getByLabelText("模型名") as HTMLInputElement).value).toBe("local");
    fireEvent.change(screen.getByLabelText("模型名"), { target: { value: "draft" } });
    fireEvent.change(screen.getByLabelText("API Key 操作"), { target: { value: "replace" } });
    fireEvent.change(screen.getByLabelText("新 API Key"), { target: { value: "private-key" } });
    expect((screen.getByLabelText("新 API Key") as HTMLInputElement).type).toBe("password");
    fireEvent.click(screen.getByText("取消"));
    await open();
    expect((screen.getByLabelText("模型名") as HTMLInputElement).value).toBe("local");
    expect(screen.queryByLabelText("新 API Key")).toBeNull();
    expect(service.save).not.toHaveBeenCalled();
  });
  it("requires an explicit key decision when changing endpoint", async () => {
    const service = api();
    render(<SettingsPanel api={service} />);
    await open();
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://example.com/v1" } });
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByText(/更换地址时/);
    expect(service.save).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("API Key 操作"), { target: { value: "clear" } });
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByText(/设置已保存/);
    expect(service.save).toHaveBeenCalledWith({ base_url: "https://example.com/v1", model: "local", key_action: "clear" });
  });
  it("redacts errors and clears a failed replacement secret", async () => {
    const service = api();
    vi.mocked(service.save).mockRejectedValue(new Error("private-key"));
    render(<SettingsPanel api={service} />);
    await open();
    fireEvent.change(screen.getByLabelText("API Key 操作"), { target: { value: "replace" } });
    fireEvent.change(screen.getByLabelText("新 API Key"), { target: { value: "private-key" } });
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByText(/保存未确认/);
    expect(screen.queryByText("private-key")).toBeNull();
    expect((screen.getByLabelText("新 API Key") as HTMLInputElement).value).toBe("");
    expect((screen.getByLabelText("模型名") as HTMLInputElement).value).toBe("local");
    expect(service.save).toHaveBeenCalledWith({ base_url: stored.base_url, model: "local", key_action: "replace", api_key: "private-key" });
  });
  it("retries read failure without overwriting configuration", async () => {
    const service = api();
    vi.mocked(service.get).mockRejectedValueOnce(new Error("secret"));
    render(<SettingsPanel api={service} />);
    await screen.findByText(/无法读取模型设置/);
    expect(screen.queryByRole("form")).toBeNull();
    fireEvent.click(screen.getByText("重试读取设置"));
    await open();
    expect((screen.getByLabelText("模型名") as HTMLInputElement).value).toBe("local");
    expect(service.save).not.toHaveBeenCalled();
  });
  it("rejects invalid input and supports Escape cancellation", async () => {
    const service = api();
    render(<SettingsPanel api={service} />);
    await open();
    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "file:///test" } });
    fireEvent.click(screen.getByText("保存设置"));
    await screen.findByRole("alert");
    expect(service.save).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByLabelText("模型名"), { key: "Escape" });
    expect(screen.queryByRole("form")).toBeNull();
  });
});
