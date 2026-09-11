# 8.6 补修：仓库摘要后的源码读取

用户反馈显示上一版在读到 README 后仍会索要 package.json、app/、packages/、具体测试文件。原因是固定摘要工具没有按路径读取参数，Runtime 在读取后强制收敛；此外提示要求先确认全部调用链过于保守。

现在 `read_github_project` 除 url 外可接受：

```json
{"url":"https://github.com/owner/repo","paths":["package.json","app","packages","tests/app-indexer.test.mjs"],"ref":"main"}
```

paths 最多四个仓库相对路径，ref 可省略使用默认分支。目录返回最多 25 项，文件返回最多 2,400 字符；返回 next_offset 时可用 offset 续读。读取基于固定 GitHub API，URL 路径编码，不跟随远端下载链接，不克隆/执行仓库。二进制、空文件、缺失或不支持对象明确返回错误，结果总量仍有限制，不能声称完整读取。

只有配置 Schema 声明 paths 的仓库工具才启用连续补读，最多四批工具后收敛；搜索仍受三批限制。不能保证所有大型项目都在预算内读完，但模型可把从真实入口追踪调用链作为用户学习事项，不需要事先穷尽实现。

已有用户自定义 tool-settings.json 继续覆盖内置配置；旧 Schema 若仅含 url，不会自动获得 paths。应由用户更新该工具定义或备份后选择恢复默认，不擅自覆盖配置。新版内置 Skill 同步说明补读能力。

测试使用模拟 GitHub HTTP 和模型，不根据反馈中的 Obelisk 描述断言仓库事实；未获取具体项目源码或调用真实模型。
