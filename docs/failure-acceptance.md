# 故障路径自动化验收

本项使用模拟 Provider、工具故障注入和临时 SQLite，不调用真实模型、不读取用户密钥，也不修改用户数据库。两种调用模式均覆盖：`native` 与 `prompt_compat`。

| 场景 | 验收要点 | 测试文件 |
| --- | --- | --- |
| 模型请求失败 | 安全错误码、Session 失败、无 Todo；用户显式重试后成功，重复消息不重复执行 | `backend/tests/test_failure_acceptance.py` |
| 非法结构化输出 | 只修复一次并追加提示；修复成功可提交，仍非法则失败且无 Todo | 同上 |
| 修复过程中取消 | 取消向 Provider 传播，资源关闭，历史保留，无 Todo；可显式重试 | 同上 |
| 更新提交失败 | 事务回滚，原主题、子项 ID 和完成状态均保留；保留待提交操作，新 Service 可免模型重试 | 同上 |
| Tool 失败 | 并行工具中一个失败时取消同批其余调用，记录终态、释放资源，不提交 Todo | `backend/tests/test_runtime_tool_failures.py` |
| Tool 执行中取消 | 工具收到取消，Session 和事件收敛为取消状态，无 Todo | 同上 |
| Tool 成功后数据库提交失败 | 不部分写入；新 Service 重试待提交操作时不重复调用工具或模型，仅创建一个 Todo | 同上 |

新增文件包含 10 个参数化用例，工具组合文件已有 6 个用例。其他执行阶段的取消、并发修改保护和待提交恢复由 `backend/tests/test_agent_runtime.py` 回归覆盖。

从项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_failure_acceptance.py backend/tests/test_runtime_tool_failures.py backend/tests/test_agent_runtime.py -q
```

范围限制：这里验证应用执行链与事务语义，不等同于真实服务商兼容性、桌面点击验收、磁盘满/断电或进程强杀测试。数据库故障是在事务提交前注入 SQLAlchemy 异常；安全错误断言检查返回的错误结构，不要求删除合法保存的用户历史。
