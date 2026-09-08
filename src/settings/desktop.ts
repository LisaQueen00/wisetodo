import { invoke } from "@tauri-apps/api/core";

export type SettingsView = { base_url: string; model: string; has_api_key: boolean };
export type SettingsUpdate = { base_url: string; model: string } & (
  | { key_action?: "keep" | "clear"; api_key?: never }
  | { key_action: "replace"; api_key: string }
);
export interface SettingsApi {
  get(): Promise<SettingsView | null>;
  save(settings: SettingsUpdate): Promise<SettingsView>;
}

function decode(result: unknown): SettingsView | null {
  if (result === null || typeof result !== "object" || !("settings" in result)) {
    throw new Error("Invalid settings response");
  }
  const value = result.settings;
  if (value === null) return null;
  if (typeof value !== "object" || Array.isArray(value)
    || Object.keys(value).sort().join(",") !== "base_url,has_api_key,model"
    || !("base_url" in value) || typeof value.base_url !== "string"
    || !("model" in value) || typeof value.model !== "string"
    || !("has_api_key" in value) || typeof value.has_api_key !== "boolean") {
    throw new Error("Invalid settings response");
  }
  return { base_url: value.base_url, model: value.model, has_api_key: value.has_api_key };
}

export const desktopSettingsApi: SettingsApi = {
  async get() { return decode(await invoke("settings_get")); },
  async save(settings) {
    const result = decode(await invoke("settings_save", { settings }));
    if (result === null) throw new Error("Missing saved settings");
    return result;
  },
};
