# 规划规则验收

本组用例验证“真实结构优先、实际事项兜底、不按时间切分”。
用例与参考结果保存在 [planning_cases.json](../backend/tests/fixtures/planning_cases.json)，每项 `reject` 描述不可接受的行为。参考结果不是唯一合法措辞。

## 自动化范围

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_planning_contract.py backend/tests/test_agent_prompts.py backend/tests/test_skill_examples.py backend/tests/test_reading_book.py backend/tests/test_github_tools.py backend/tests/test_github_skills_runtime.py -q
```

不访问真实模型或 GitHub，不读取用户凭据。验证两种模型交互模式、决策/最终阶段均保留核心规则和完整 Skill，以及参考输出经过 Runtime 后不被改写，澄清不创建 Todo。既有 PDF/GitHub 测试验证只读工具资料回传。

这不是模型语义验收：模拟 Provider 按预定内容返回，不能证明真实模型不会编造、排期或误选 Skill。生产端 Schema 不判定语义，不使用“第一天”等关键词黑名单（真实标题可能包含时间词）。

## 按需人工验收（尚未执行）

仅在用户主动确认后进行，避免自动消耗 Token。安装三个业务 Skill，在新会话粘贴对应 `input`。这些用例不需要联网工具；每例通常一次模型调用，格式修复可能增加一次调用。不要点击测试连接或额外重试。

| 用例 | 主要检查 |
| --- | --- |
| book_chapters | 保留真实章节、标题和顺序，无周计划或空泛附加事项 |
| book_missing_structure | 请求目录，不编造章节或用前半本/后半本凑数 |
| book_single_section | 请求真实小节或扩大范围，不强加笔记以凑两个子项 |
| time_in_real_title | 保留小说章节“第一天”“第二天”，不误当排期删除 |
| project_actual_entry | 使用已确认的示例与入口，不虚构数据库或内部函数 |
| practical_fallback | 直接拆分回收、分类归档等实际行动，不索要不存在的目录 |
| documentation_contribution | 围绕文档修订与文档 PR，不机械套用代码修复模板 |
| multiple_targets | 先请用户选一个目标，不批量创建或合并两个独立目标 |

验收同时检查：每个创建操作只有一个 Todo、至少两个子项，默认未完成；澄清不写入 Todo。遇到语义问题时记录用例 ID、模型名称和结果，隐去凭据，调整提示词后由用户决定是否重新调用。不要把自动化通过写成真实模型验收通过。
