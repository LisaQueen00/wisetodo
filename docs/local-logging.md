# 本地诊断日志

Python Sidecar 启动时在 SQLite 数据库同目录的 `logs/wisetodo.log` 写入 UTF-8 JSON Lines。无需配置或联网，不上传日志。默认单文件上限 1 MiB，最多保留 `.1`、`.2`、`.3` 三份轮转备份，合计约 4 MiB。

每条只允许：UTC 时间 `time`、预定义事件 `event`、可选的 WiseTodoError 枚举 `code`。例如：

```json
{"time":"2026-09-10T08:00:00+00:00","event":"ipc_failed","code":"FILE_UNAVAILABLE"}
```

## 记录范围

- 后端启动、停止、初始化失败或运行失败。
- IPC 成功、失败、非法输入与重复请求拒绝。
- 工具开始、完成、失败、取消。
- 保存成功后旧凭据清理失败（不会把已完成保存改为失败）。

接口只接受 Event/ErrorCode 枚举，**不接受自由文本**。不记录 API Key、配置、用户消息、模型回复、提示词、工具参数/结果、文件正文、路径、URL、请求 ID、Todo/Session ID、原始异常或堆栈。它是粗粒度诊断，不是完整调用追踪或操作审计。

使用独立文件 handler，不订阅根日志或 SDK 日志，避免第三方将请求内容写入该文件。stdout 仍仅供 JSON IPC，不重定向进日志。现有开发终端 stderr、浏览器控制台、Rust 原生错误及系统崩溃报告不在本文件采集范围内；不要把“本文件安全”当作所有外部日志均已审计。

## 生命周期与故障

启动失败时只向 stderr 输出固定诊断，不打印底层异常。文件初始化不可用时禁用本地日志，业务照常尝试启动；运行中磁盘满或轮转失败时忽略日志写入错误，不因记录失败导致 Todo 操作失败。正常退出关闭文件，强制终止时最后事件可能缺失。当前没有专门的日志故障 UI。

单 Sidecar 写入，不支持多个进程共享同一日志文件并并发轮转。默认复用系统应用目录权限，不提供加密。检查初始路径是否为符号链接/junction，但不构成对恶意实时文件替换的 OS 沙箱。`logs/` 已在 `.gitignore` 中忽略。

如需清理，先正常退出应用，再删除 `logs/` 内的 `wisetodo.log` 及其三份轮转文件，不影响 Todo 数据库或模型配置；下一次启动会重建。

## 离线验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_diagnostics.py backend/tests/test_settings_storage.py -q
```

使用临时目录、模拟错误、模拟凭据和真实本地 Sidecar，不读取用户密钥、不调用模型。检查敏感字段不落盘、stdout 协议保持、轮转数量限制及日志失败不影响业务。
