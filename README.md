# WiseTodo

一个留在桌面上的待办清单，把想做的事变成可以逐项完成的行动。

WiseTodo 将日常 Todo 与 Agent 辅助规划放在同一个紧凑桌面面板中：手动管理任务，或提供项目链接、阅读资料，让 Agent 读取信息并整理子项。任务按实际组成和逻辑顺序拆分，不默认按天、周安排。

[安装与使用](docs/getting-started.md) · [构建与打包](docs/building.md) · [主题指南](docs/themes.md) · [参与贡献](CONTRIBUTING.md)

## 功能

- **桌面待办**：紧凑面板、可选置顶、背景透明度调节和系统托盘；Chat 从右侧滑入并覆盖 Todo，用完即可收起。
- **任务管理**：创建、编辑、删除、手动排序和两级优先级。每个 Todo 至少两个子项，进度随勾选计算，全部子项完成后任务完成。
- **辅助规划**：围绕一个目标对话、澄清并创建或修改 Todo，保留历史会话与工具执行记录。Agent 不删除顶层任务。
- **资料读取**：内置公开网页、GitHub 项目和本地 PDF 等只读工具，用于开源项目学习、章节阅读计划等场景，详见 [工具说明](docs/web-and-builtin-tools.md)。
- **可扩展能力**：通过 Skill 指导任务处理，通过 Tool 配置接入本地处理器、HTTP API 或 MCP 服务。
- **自定义主题**：JSON 导入、导出和预览，支持组件配色、渐变、字体及加粗、倾斜等文字样式。

## 开始使用

当前为 **0.1.0 测试阶段**，尚未正式发布。Windows 已生成本地测试包；macOS 与 Linux 已配置原生构建流程，仍待 CI 和实机验收。当前产物未签名，不承诺所有平台已经验证可用。

测试包可从维护者运行成功的 GitHub Actions → **Desktop builds** → **Artifacts** 获取；对应平台构建未成功前，不会有可用产物。也可以按 [构建说明](docs/building.md) 从源码生成。

| 平台 | 打包目标 | 打开方式 |
| --- | --- | --- |
| Windows x64 | NSIS 安装包 / 直接运行 ZIP | 安装后从开始菜单打开；或完整解压 ZIP 后运行 `wisetodo.exe`，保留同目录 Sidecar |
| macOS Apple Silicon | DMG | 将完整 `.app` 拖入应用程序目录；系统安全限制见使用指南 |
| Linux Debian/Ubuntu x64 | DEB | 安装后从应用菜单打开 |

普通用户无需安装 Python、Node.js 或 Rust。运行时依赖、安装、退出与升级步骤见 [安装与使用](docs/getting-started.md)。

### 第一个任务

1. 直接手动新建 Todo，填写内容和至少两个子项；手动功能不依赖模型。
2. 要使用辅助规划，打开 Chat，在 Settings 中填写 Base URL、模型名及所需 API Key 并保存。
3. 描述一个目标，例如“学习这个 GitHub 项目”，附上项目地址；或把 PDF 拖入输入框，说明希望生成章节阅读待办。
4. 按需回答澄清问题。成功创建或修改后，在 Todo 区查看结果，也可以继续手动调整。

一次成功的规划处理一个 Todo；完成后的会话只读，新的操作请新建会话。资料可能受权限、网络和工具读取范围限制，模型生成的计划仍需自行核对。

## 数据与隐私

Todo、会话和设置保存在本机；API Key 使用系统凭据库留存。再次打开通常不需要重新配置，相同设备升级后保留已有数据是正常行为。

**本地保存不等于所有处理离线。** 使用远程模型或联网工具时，请求内容及相关资料会发送给所配置的服务。模型服务可能收费，连接测试也可能产生少量费用。请勿在仓库或问题反馈中提交密钥、个人数据库或敏感资料。

构建产物不包含开发者的个人配置或数据库；构建目录、虚拟环境和本地工作笔记不纳入版本控制。

## 本地开发

技术栈：React + TypeScript + Tailwind CSS，Tauri 2 桌面外壳，Python Sidecar，LangGraph，SQLite / SQLAlchemy / Alembic。

先按 [平台环境准备](docs/building.md) 安装 Python 3.12、Node.js 22、pnpm 10、Rust 和系统依赖。Windows 下在项目根目录运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "./backend[dev]"
pnpm.cmd install --frozen-lockfile
pnpm.cmd tauri dev
```

已有 `.venv` 时无需重建。macOS/Linux 对应命令见构建指南。`pnpm dev` 仅启动浏览器前端，不等同于完整桌面程序。

生成本机分发包：

```powershell
.\.venv\Scripts\python.exe scripts/build_release.py
```

默认产物位于 `src-tauri/target/release/bundle/`；设置 `CARGO_TARGET_DIR` 时以该目录为准。各平台须原生构建，完整流程及 CI 使用方式见 [打包说明书](docs/building.md)。

## 文档与贡献

- [安装与首次使用](docs/getting-started.md)：下载、打开、设置、升级和校验。
- [构建与打包](docs/building.md)：三平台环境、命令和产物目录。
- [主题指南](docs/themes.md)：主题 JSON 与组件样式。
- [Skill / Tool 配置](docs/tool-setup.md)：扩展与覆盖内置能力。
- [贡献指南](CONTRIBUTING.md)：开发检查、测试和提交注意事项。
- [发布检查清单](docs/releasing.md) · [更新记录](CHANGELOG.md)。

欢迎反馈问题和讨论改进。请附上系统与架构、应用版本、复现步骤、预期和实际行为；截图与日志请先脱敏。涉及模型调用的测试优先使用模拟响应，避免无意产生费用。

## 许可证

项目尚未选定许可证。源码可见不等于已授予开源使用、修改或再分发许可；正式发布前需完成许可证选择与第三方依赖声明审查。
