# 数据库迁移验收

迁移由 `initialize_database` 在 Sidecar 接受请求前执行 `upgrade head`，不是业务代码导入 `env.py`。本轮只增加测试，不修改已有迁移版本。

自动化范围（全部使用临时 SQLite）：

- 从 0001、0002、0003 分别经应用初始化入口升级到当前 0004，并重复打开。
- 0003 中已有会话、消息和工具事件升级后保留原字段、内容和时间；新增执行字段为 NULL，外键检查通过。
- 启动工作目录与项目不同，数据库路径含中文、空格、百分号时仍正确定位迁移和数据库。
- 未知版本号、非 SQLite 内容拒绝初始化，不覆盖原文件。
- 复用既有测试，验证新库建表、表约束、ORM 元数据一致性、升级与降级后已有 Todo 保留。

运行命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_migration_acceptance.py backend/tests/test_database.py backend/tests/test_session_tables.py backend/tests/test_todo_tables.py -q
```

本轮结果：32 项通过，其中新增 7 项。不使用真实模型或用户数据库。

边界：测试不代表断电、磁盘满或任意迁移中途失败都能自动回滚。SQLite DDL 不应一概视为事务性的；升级前应备份已关闭连接的数据库。应用没有自动降级功能，手工 downgrade 会丢失被删除的字段或表；既有降级测试只证明指定保留数据仍在，不承诺无损降级。打包后的迁移资源定位仍需发布包验收。
