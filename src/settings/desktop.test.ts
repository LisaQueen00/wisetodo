import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { desktopSettingsApi } from "./desktop";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
const view = { base_url: "http://localhost:8000/v1", model: "test", has_api_key: true };
beforeEach(() => vi.resetAllMocks());

describe("desktop settings", () => {
  it("reads absent and configured settings", async () => {
    vi.mocked(invoke).mockResolvedValueOnce({ settings: null }).mockResolvedValueOnce({ settings: view });
    expect(await desktopSettingsApi.get()).toBeNull();
    expect(await desktopSettingsApi.get()).toEqual(view);
    expect(invoke).toHaveBeenCalledWith("settings_get");
  });
  it("sends explicit replace and clear, or keeps a key by omission", async () => {
    vi.mocked(invoke).mockResolvedValue({ settings: view });
    const base = { base_url: view.base_url, model: view.model };
    await desktopSettingsApi.save({ ...base, key_action: "replace", api_key: "secret" });
    expect(invoke).toHaveBeenLastCalledWith("settings_save", { settings: { ...base, key_action: "replace", api_key: "secret" } });
    await desktopSettingsApi.save({ ...base, key_action: "clear" });
    expect(invoke).toHaveBeenLastCalledWith("settings_save", { settings: { ...base, key_action: "clear" } });
    await desktopSettingsApi.save(base);
    expect(invoke).toHaveBeenLastCalledWith("settings_save", { settings: base });
  });
  it.each([{}, { settings: [] }, { settings: { ...view, api_key: "secret" } }, { settings: { ...view, has_api_key: "true" } }])("rejects malformed or secret-bearing responses", async (result) => {
    vi.mocked(invoke).mockResolvedValue(result);
    await expect(desktopSettingsApi.get()).rejects.toThrow("Invalid settings response");
  });
  it("does not accept null as successful save", async () => {
    vi.mocked(invoke).mockResolvedValue({ settings: null });
    await expect(desktopSettingsApi.save({ base_url: view.base_url, model: view.model })).rejects.toThrow("Missing saved settings");
  });
});
