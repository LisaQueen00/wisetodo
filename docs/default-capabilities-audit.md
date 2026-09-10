# 安装版默认能力核查（Phase 8.4）

## 当前结论

干净安装没有基础工具配置和 Skill，模型因此看不到读取能力。Python handler 已存在并不等于它已成为模型可调用的工具。本记录是修复前核查，不表示默认能力已接通。

1. `scripts/build_sidecar.py` 收集 Python 代码与依赖、Alembic 配置和迁移；没有显式收集仓库根目录的 `skills/`、`examples/`。
2. `backend/wisetodo/main.py` 默认从应用数据目录的 `tool-settings.json`、`skills/` 加载，没有内置默认资源回退。
3. `tools/source.py` 在可选配置不存在时返回空 ToolRegistry；这是当前默认启动方式。
4. `tools/local_handlers.py` 注册了 `parse_pdf`、`read_github_project`、`search_projects`，但只提供实现映射，不自动生成配置或注册模型工具定义。
5. Runtime 使用 `registry.definitions()` 组装模型请求；空 Registry 就没有可用工具。工具调用回到同一 Registry 与 handler 映射执行，链路本身已存在。
6. `SkillSource` 从指定目录建立 Run 快照；空目录没有 Skill。Skill 文字不能凭空添加工具，模型自身也不能被假设为自带联网能力。

## 离线核对

使用临时空目录、实际加载器与注册函数：

- handler：`parse_pdf`、`read_github_project`、`search_projects`。
- 默认可见工具：0；匹配 GitHub URL 的 Skill：0。
- 显式加载 `examples/github-tools.json`：出现 `read_github_project`、`search_projects`。
- `test_tool_source.py` 与 `test_runtime_tools.py` 合计 7 项通过。

没有读取用户模型配置、调用模型或执行网络工具。此核查在源码加载器完成，未把“手动配置能通过测试”当作“安装版默认可用”。

## 后续实现边界

- 将经过审查的基础工具定义和首批 Skill 作为只读内置资源打包；干净安装默认可用，不复制用户数据库或模型配置。
- 在加载层处理默认值、用户覆盖和禁用，不能在升级时覆盖用户文件；明确现有空配置的兼容语义，避免自动重新启用用户有意禁用的工具。
- 保持每个 Run 的快照与模型可见定义、实际执行 Registry 一致，提交重试不重新调用工具。
- 未知 MCP 服务不默认启用；通用网页读取和搜索后依赖式读取仍属于后续子项，不因装配完成就宣称已经支持。
- 修复后必须加入干净目录下模型请求包含内置工具的回归，以及冻结程序资源可用性检查；最后重建安装包验收。
