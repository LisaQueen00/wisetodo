# 开源项目学习工具链

首版按需工具，不是固定的八步工作流。默认工具总数从 4 增为 12，旧 read_github_project 仍可用。已有 tool-settings.json 继续完全覆盖默认值，不自动写入新工具；配置文件不存在时才使用新版默认值。

| 工具 | 实际能力 | 边界/续读 |
| --- | --- | --- |
| inspect_github_project | 固定版本、概况、README、根目录 | README 摘录，目录前 25 项 |
| list_github_tree | 指定目录 | 25 项/page；上游 Contents 最多 1000 项，非递归 |
| read_github_file | 文本文件按行读取 | start_line / next_line，80 行或 8000 字符；超长单行标记裁剪 |
| search_github_code | 固定 commit 的字面、区分大小写搜索 | path 限定目录，五文件/page，每文件五命中；不是 GitHub 搜索索引/符号引用 |
| inspect_github_file_symbols | Python AST 定义、作用域及行号 | 25 符号/page；128000 字符限制；不支持其他语言，不分析引用 |
| read_github_history | 固定版本祖先提交、可选 path | 十提交/page；query 只筛选当前页的提交说明，空结果可继续 next_page |
| read_github_commit | 指定完整 SHA 的说明、文件、patch | 五文件/page，patch start_line 为 diff 行号；patch 可能缺失/不完整 |
| read_github_discussion_context | 指定 issue/PR 正文与普通评论 | 五评论/page，正文/评论摘录；不含行内评审，不固定历史快照 |

另外保留 search_projects、read_url、parse_pdf 和旧仓库工具。

## 共同约束

同一个 Run 的新工具共享 RepositoryReader。首次将 ref（省略为默认分支）解析到完整 commit；后续相同 ref 固定到该版本。模型应继续传入返回的 commit，避免主动切换版本。同 Run 的缓存最多 4 MiB；缓存满后不再缓存新响应，没有磁盘源码缓存、不 clone、不安装依赖、不执行仓库代码。新 Run 重新解析；旧兼容工具不共享新版 snapshot。

所有请求复用固定 GitHub API 的 GET、无自动重定向、单响应 1 MiB 限制；上游限流、超大响应、不可访问仍可能中断。递归树被截断时显式标记；体积超限时明确失败，不保证大仓库全量搜索。路径禁止穿越、任意 URL 和控制字符。返回资料均是不可信文本。

Runtime 给新链路最多八批，但请求重复或结果完全重复即收敛；每批可以含多个独立调用。单次工具执行仍有超时和取消，模型结果修复额度不变。该机制不是语义进展判断，足够资料时仍靠提示词要求立即生成。最坏情况下新增补读会增加模型调用，测试只使用模拟 Provider。

## 尚未覆盖

- JS/TS 等语言级符号解析、跨文件定义/引用、完整调用图。
- 大仓库本地索引、完整递归目录分页、全仓库高速检索。
- 历史 diff 全文搜索、重命名追踪、函数演进、PR 行内评审与自动关联提交。
- 仓库代码运行与测试执行（需要单独的安全方案）。

## 协议依据

实现依据 [GitHub Contents](https://docs.github.com/en/rest/repos/contents)、[Git Trees](https://docs.github.com/en/rest/git/trees)、[Commits](https://docs.github.com/en/rest/commits/commits) 和 [Issue comments](https://docs.github.com/en/rest/issues/comments)；不调用需要另配身份的代码搜索来伪装匿名搜索可用。query 的历史筛选在本地完成，API 不提供这里所说的函数演进分析。
