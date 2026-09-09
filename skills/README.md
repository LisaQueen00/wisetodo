# WiseTodo 业务 Skill 示例

这些文件由 WiseTodo 的 Skill 加载器读取，不是 Codex 扩展。当前生产 Runtime 尚未自动装配加载入口；示例存在不代表相关工具已实现。

- `reading-book`：按真实章节阅读书籍。
- `learn-github-project`：按项目实际入口与模块学习代码。
- `join-open-source`：先确定一个贡献目标，再组织具体事项。

`accepts` 是候选筛选用的对象类型，不是用户意图。`book_url`、`github_url` 等类型需要输入链路识别，不能只靠任意 URL 推断。纯文本只使贡献 Skill 成为候选，其正文要求明确的贡献意图。

`parse_pdf`、`read_url`、`search_projects` 是待实现、待与 Tool Registry 对齐的工具名。示例允许用户直接提供资料，也允许多种读取路径，因此使用 optional；并非允许编造缺失资料。一个 Skill 若无法在缺少某工具时工作，才应将它列为 required。缺少 required 会使该 Skill 被过滤。

修改保存后，下一次 `SkillSource.begin_run()` 才读到新内容，已返回的快照不变。这里只提供提示词示例；本地测试验证格式、筛选和注入，不证明真实模型执行效果。Phase 5 仍需工具接入和业务验收。
