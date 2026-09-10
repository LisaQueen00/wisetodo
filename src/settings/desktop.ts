import { invoke } from "../errors/invoke";

export type SettingsView = { base_url: string; model: string; has_api_key: boolean };
export type SettingsUpdate = { base_url: string; model: string } & (
  | { key_action?: "keep" | "clear"; api_key?: never }
  | { key_action: "replace"; api_key: string }
);
export interface SettingsApi {
  test?(): Promise<string>;
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
  async test() {
    const result = await invoke<unknown>("settings_test");
    if (!result || typeof result !== "object" || !("connection_test" in result)
      || typeof result.connection_test !== "string" || !Object.hasOwn(connectionMessages, result.connection_test)) {
      throw new Error("Invalid connection test response");
    }
    return result.connection_test;
  },
  async get() { return decode(await invoke("settings_get")); },
  async save(settings) {
    const result = decode(await invoke("settings_save", { settings }));
    if (result === null) throw new Error("Missing saved settings");
    return result;
  },
};

export const connectionMessages: Record<string, string> = {
  ok: "基本连接测试通过；尚未验证工具调用、结构化输出或推理能力。",
  not_configured: "请先保存模型设置。",
  settings_unavailable: "无法读取设置或系统凭据，请检查后重试。",
  authentication: "鉴权失败，请检查 API Key 或访问权限。",
  not_found: "接口或模型未找到，请检查 Base URL 和模型名。",
  rate_limited: "服务限流或额度不足，请检查服务账户后重试。",
  timeout: "连接测试超时；本地模型可能仍在加载，服务端可能继续处理并计费。",
  request_failed: "连接测试失败，请检查网络、服务及请求兼容性（需要支持 max_completion_tokens）。",
  invalid_response: "未收到完整有效的文本回复，可能是截断、拒绝或接口不兼容；不能确认测试通过。",
};
