# WiseTodo 业务 Skill 示例

这些文件由 WiseTodo 的 Skill 加载器读取，不是 Codex 扩展。生产 Runtime 从数据库同目录的 `skills/` 或显式 `--skills-dir` 加载；仓库示例不会自动复制到用户目录。

- `reading-book`：按真实章节阅读书籍。
- `learn-github-project`：按项目实际入口与模块学习代码。
- `join-open-source`：先确定一个贡献目标，再组织具体事项。

`accepts` 是候选筛选用的对象类型，不是用户意图。阅读 Skill 接受 text/pdf/url 候选以覆盖粘贴目录、PDF 和书籍链接，正文要求明确的阅读意图；不能把任意 PDF 或 URL 都当成书。`book_url` 保留给后续语义识别，当前不自动推断该类型。

`parse_pdf`、`read_github_project`、`search_projects` 已注册，配置见 [工具说明](../docs/tool-setup.md)。GitHub 工具是异步本地 handler 发起公开 API 只读请求，不是离线数据源；通用 `read_url` 仍需配置外部工具。允许用户直接提供资料，因此工具使用 optional；并非允许编造缺失资料。缺少 required 工具会使相应 Skill 被过滤。

修改保存后，下一次 `SkillSource.begin_run()` 才读到新内容，已返回的快照不变。阅读链路已用真实临时 PDF、解析子进程、模拟模型和 SQLite 验证；GitHub 学习/贡献链路使用模拟 HTTP 与模型验证，包含搜索→澄清→选定后规划。三个 Skill 均可从纯文本成为候选，按实际目的采用其一；测试不证明真实模型遵循提示词的效果。
