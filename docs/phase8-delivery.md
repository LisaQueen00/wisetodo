# Phase 8 集成交付与能力边界

当前定位：Windows x64 未签名测试版本 0.1.0。已具备可运行的核心链路，但不因开发/离线测试通过就宣布正式发布或全部实机验收完成。

## 已实现的核心能力

| 场景 | 当前交付 | 限制 |
| --- | --- | --- |
| 手动 Todo | 增删改、至少两个子项、完成进度、排序、自动保存 | 顶层完成由全部子项决定 |
| 桌面 | 窄版面板、Chat 右滑覆盖、置顶、托盘、单实例、背景透明度留存 | Windows 重点验证；系统标题栏不由主题控制 |
| 主题 | v2 组件/状态颜色、渐变、字体排版、预览/保存、JSON 导入与原生导出 | 已安装字体；字体文件导入后续；系统原生控件有边界 |
| Chat | 会话/历史、澄清、取消、真实执行入口、失败与免模型提交重试 | 一个成功会话处理一个 Todo；真实质量取决于配置模型 |
| 模型配置 | 设置页输入 URL/模型/Key、留存与手动连接测试 | 初次需要用户配置；基础连接测试不是完整能力测试 |
| PDF 阅读 | 目录层级/偏移、页面文本续读、明确截断来源 | 扫描件 OCR 不在当前范围；模型不应虚构缺失目录 |
| 网页 | 公开静态 HTTP(S) 正文、标题、链接与安全边界 | 不支持登录、验证码、浏览器动态渲染；不是通用网页搜索 |
| GitHub 学习 | 搜索定位、概览、目录分页、文件续读、有限源码搜索、历史/提交、讨论资料 | Python AST 符号；其他语言符号、完整索引、PR 行内评审后续 |

## 默认工具与覆盖规则

缺少用户配置时启用 12 个内置工具：

`read_url`、`parse_pdf`、`read_github_project`、`search_projects`、
`inspect_github_project`、`list_github_tree`、`read_github_file`、
`search_github_code`、`inspect_github_file_symbols`、`read_github_history`、
`read_github_commit`、`read_github_discussion_context`。

缺少用户 skills 目录时使用三份内置 Skill。已有 tool-settings.json 或 skills 目录完整覆盖对应默认内容，空文件配置列表/空目录表示禁用；升级不覆盖它们。自定义旧工具 Schema 不会自动获得新参数。

## 可重复的离线验收

项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
pnpm.cmd test
pnpm.cmd build
pnpm.cmd lint
.\.venv\Scripts\python.exe scripts/accept_release.py src-tauri/target/phase8-final/release/wisetodo-sidecar.exe
.\.venv\Scripts\python.exe scripts/prepare_release.py --artifact src-tauri/target/phase8-final/release/bundle/nsis/WiseTodo_0.1.0_x64-setup.exe
```

`accept_release.py` 只创建临时目录：检查空 Todo/模型设置、创建两子项 Todo、重开留存、更新子项、再次重开，以及已有非密钥模型配置、空 Tool 配置和空 Skill 目录不被改写。每个 IPC 请求均重新启动冻结程序；不使用真实用户目录、系统凭据写入、网络或模型。它不等同于 NSIS 安装/升级测试或 WebView 设置迁移。

源码回归覆盖默认工具加载、用户覆盖、依赖工具链、取消/重试、PDF 续读等；冻结检查覆盖实际打包后端持久化。两类证据不能替代真实模型质量和桌面视觉验收。

本次执行结果：后端全量 960 项、前端 210 项通过；Ruff、mypy（80 文件）、前端构建和 ESLint 通过。新集成版冻结验收通过，NSIS 与 SHA256 已生成。Windows keyring 的局部类型忽略仅补足第三方构造函数的缺失标注，不改变运行逻辑；相关 21 项回归复测通过。

## 保留的人工关卡

- 开始菜单、开机启动、PDF 工作进程及退出重开不闪窗的完整矩阵。
- 干净设备上的安装/升级/卸载、系统凭据与桌面设置留存。
- 主题导入导出、对比度、透明度、焦点、拖放和托盘恢复的完整视觉/交互验收。
- 经用户批准，少量真实模型验证具体仓库与原书；不自动重复消费 Token。
- Windows 实机性能和其他平台验证；许可证、签名与发布来源提交审查。

用户已反馈无控制台、窄版/覆盖 Chat 和主题总体效果改善；这些反馈只表示对应体验经过尝试，不替代整套人工矩阵。后续 UI 不足单独讨论，不在本次集成交付中预先改动。

## 本地交付物

集成版 EXE：`src-tauri/target/phase8-final/release/wisetodo.exe`。
NSIS：`src-tauri/target/phase8-final/release/bundle/nsis/WiseTodo_0.1.0_x64-setup.exe`，校验文件同目录。
运行 EXE 前退出托盘旧版，保留同目录 Sidecar。构建目录被 Git 忽略；个人数据库、凭据和主题不随包分发。
