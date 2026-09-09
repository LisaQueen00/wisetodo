# Skill 与 Tool 配置（Phase 4）

应用从 SQLite 所在目录读取 `skills/*/SKILL.md` 和 `tool-settings.json`。
默认目录/文件可在启动后创建，下一个需要模型的 Run 会发现它们；运行中的快照不变。
缺失默认 Tool 文件按无工具运行，损坏文件报错，不静默忽略。
Sidecar 可用 `--skills-dir`、`--tool-config` 指定绝对路径；显式 Tool 文件缺失会报错。
仓库 `skills/` 是可复制的示例，不会自动安装到用户目录。

## MCP 配置示例

```json
{
  "tools": [{
    "name": "read_document",
    "description": "读取文档目录",
    "input_schema": {
      "type": "object",
      "properties": {"document": {"type": "string"}},
      "required": ["document"],
      "additionalProperties": false
    },
    "transport": {"type": "mcp", "server": "documents", "tool": "read_document"}
  }],
  "servers": [{
    "name": "documents",
    "connection": {"type": "streamable_http", "url": "http://127.0.0.1:8000/mcp"}
  }]
}
```

这只是配置格式，不附带该服务。工具名与参数必须对应真实服务。
stdio 连接使用 `{"type":"stdio","command":"可信可执行文件路径","args":[]}`。
所有端点和命令必须由用户审核，声明只读不是权限沙箱。

## local 注册入口

在 `backend/wisetodo/tools/local_handlers.py` 的 `registered_handlers()` 中登记经过审核的异步函数。
函数接收 JSON 参数对象，返回 JSON 值，须支持取消且不能阻塞事件循环。
配置使用 `{"type":"local","handler":"已注册名称"}`。
可以通过配置新增已注册 handler 的工具别名；不能从配置导入任意 Python 模块。
当前白名单包含 `parse_pdf`，由 Runtime 绑定本次用户附件引用；新代码需更新应用，外部扩展可使用 MCP。

## 阅读 PDF

将仓库 `skills/reading-book/` 复制到数据库同目录 `skills/reading-book/`，或指定仓库 `skills/` 的绝对路径作为 `--skills-dir`。
将 [reading-tools.json](../examples/reading-tools.json) 作为 `tool-settings.json` 使用；已有配置时只合并其 `tools` 项，不覆盖其他工具。下一个 Run 生效。

将一本 PDF 拖入 Chat 输入框，发送“按这本书的真实章节生成阅读任务”。
模型只收到文件名与本次 Run 的 `file_ref`；`parse_pdf` 只接受这个引用，不能读取模型指定的任意路径。
解析在只读子进程中执行，25 秒超时或取消后终止并回收进程；保留原有 64 MiB 输入、有限目录/开头文本与输出预算。
这是可取消的进程隔离，不是 OS 权限沙箱，也没有跨平台硬内存上限；暂不做 OCR。
有效书签目录可用于按章节创建一个 Todo，无可用目录或无效/加密 PDF 时应请求用户补充资料。
用户已经粘贴真实目录时可直接规划，无需调用解析工具。

配置不会自动安装，测试不调用真实模型；打包后的子进程入口仍需随发布阶段验证。

## 凭据安全配置

在仓库根目录使用项目虚拟环境执行：

```powershell
.\.venv\Scripts\python.exe -m wisetodo.tools.credential_cli add
```

按隐藏输入提示输入 Bearer token，成功只输出 UUID。将 UUID 填入 HTTP 工具的
`transport.credential_ref` 或 MCP Streamable HTTP 的 `connection.credential_ref`。
密钥保存在系统凭据库 `WiseTodo.Tools`，不要把密钥写入参数、配置、聊天或源码。
无法安全隐藏输入或系统凭据库不可用时命令失败，不回退到明文文件。

更换密钥：先 add 新凭据，再修改引用，最后删除旧凭据：

```powershell
.\.venv\Scripts\python.exe -m wisetodo.tools.credential_cli delete UUID
```

删除会使仍引用旧 UUID 的后续调用失败；不会自动编辑配置。暂无凭据管理 UI 或 stdio 密钥注入。
此命令当前要求项目 Python 环境，打包后的管理入口留在发布阶段。

## 验证范围

自动化验证使用模拟模型、临时 SQLite、注册本地测试函数及本地 MCP 服务，不消耗模型 Token。
覆盖热加载、当前 Run 隔离、故障取消和免模型提交重试。
不等于真实模型规划效果、所有系统凭据库或三平台安装包验收。
