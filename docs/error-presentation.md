# WiseTodo 错误展示

后端错误码来自 `backend/wisetodo/errors.py`。前端统一中文映射在 `src/errors/messages.ts`，自动化测试对照两个集合，新增或删除错误码必须同步维护。

## 桌面链路

Python WiseTodoError → Rust 提取 code/retryable → Todo、Session、Settings 的 invoke 适配器 → 应用内“最近一次操作提示”。

Rust 不向这个错误通道转发 message、details 或 user_message；前端仅显示本地维护的文案，未知错误码使用内部错误提示。未知传输异常不原样显示，原操作区仍保留读取失败、输入保留等兜底说明。接口仍使用 Rust String 错误返回，但内容是最小 JSON 对象，正常成功响应未变。

提示包括错误码和处理方向，可手动关闭；它是最近一次失败记录，不代表后台当前状态。retryable 仅用于说明可手动重试，不新增自动请求、不改变已有 Session 状态机。RUN_CANCELLED 使用 status 而不是 alert，不显示重试建议。

工具历史中含错误码时使用同一映射；旧记录只有 user_message 时沿用已有的限长展示，不展示原始结果、参数、堆栈或 details。本次不迁移历史、不新增错误持久化，不把桌面窗口错误或连接测试状态硬塞进 WiseTodoError 枚举。

## 验证

```powershell
pnpm.cmd test
pnpm.cmd lint
pnpm.cmd build
& C:/Users/pc/.cargo/bin/cargo.exe test --manifest-path src-tauri/Cargo.toml --offline
```

覆盖全部 27 个错误码显示/关闭、取消状态、未知码、敏感字段丢弃、无自动重试及真实本地 Python IPC 的错误码传递。测试使用模拟错误或未配置模型的临时数据库，不访问真实模型或读取用户凭据。
