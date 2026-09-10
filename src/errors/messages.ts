export const errorMessages = {
  SETTINGS_VALIDATION_FAILED: "模型设置无效，请检查地址、模型名和密钥操作。",
  SETTINGS_READ_FAILED: "无法读取模型设置或系统凭据，请检查设置后重试。",
  SETTINGS_SAVE_FAILED: "设置保存未确认，请重新读取核对，不要假定已经保存。",
  SESSION_RETRY_UNAVAILABLE: "当前会话不能重试，请刷新历史确认状态。",
  SESSION_RETRY_FAILED: "会话重试失败，请刷新历史检查执行结果。",
  SESSION_READ_ONLY: "此会话已完成，只能查看；其他操作请新建会话。",
  SESSION_VALIDATION_FAILED: "会话输入无效，请检查内容和附件。",
  SESSION_NOT_FOUND: "会话已不存在，请刷新历史或新建会话。",
  SESSION_READ_FAILED: "读取会话失败，请刷新历史。",
  SESSION_SAVE_FAILED: "会话保存未确认，请刷新历史核对后再操作。",
  MODEL_REQUEST_FAILED: "模型请求失败，请检查连接、服务状态或额度。",
  MODEL_CAPABILITY_INSUFFICIENT: "模型不支持所需能力，请检查模型设置或更换模型。",
  INVALID_AGENT_OUTPUT: "模型输出未通过校验，本次未提交 Todo，请调整需求或模型。",
  TOOL_NOT_FOUND: "所需工具不可用，请检查工具注册和配置。",
  TOOL_ARGUMENT_INVALID: "工具参数无效，未执行该调用，请检查参数定义或调整需求。",
  TOOL_EXECUTION_FAILED: "工具执行失败，本次未提交 Todo，请检查资料、工具配置或服务。",
  TODO_VALIDATION_FAILED: "待办数据无效或已发生冲突，请重新读取并检查标题、至少两个子项及排序范围。",
  TODO_NOT_FOUND: "目标 Todo 或子项已不存在，请重新读取列表。",
  TODO_SAVE_FAILED: "Todo 保存未确认，请重新读取核对后重试。",
  TODO_READ_FAILED: "读取 Todo 失败，请重新读取列表。",
  IPC_METHOD_NOT_FOUND: "应用接口不匹配，请重启应用并检查版本。",
  IPC_INVALID_REQUEST: "应用请求无效，请重试操作或重启应用。",
  RUN_CANCELLED: "已停止执行。",
  CONTEXT_TOO_LARGE: "资料超出上下文预算，请缩小资料范围或新建会话。",
  FILE_UNAVAILABLE: "附件不存在、已移动或无法访问。请恢复原路径后重试，或新建会话重新附加文件。",
  FILE_REFERENCE_INVALID: "附件路径或引用不受支持，请重新附加普通本地文件。",
  INTERNAL_ERROR: "处理操作时发生内部错误，请核对当前状态后重试。",
} as const;

export type ErrorCode = keyof typeof errorMessages;
export interface UiError { code: ErrorCode; retryable: boolean }
export function decodeError(value: unknown): UiError | undefined {
  if (typeof value === "string") {
    if (value.length > 4096) return undefined;
    try { value = JSON.parse(value); } catch { return undefined; }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const data = value as Record<string, unknown>;
  if (typeof data.code !== "string") return undefined;
  return {
    code: Object.hasOwn(errorMessages, data.code) ? data.code as ErrorCode : "INTERNAL_ERROR",
    retryable: data.retryable === true,
  };
}
