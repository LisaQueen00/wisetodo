# 三平台构建

本流程生成未签名测试安装包，不自动发布版本。GitHub Actions 的 `Desktop builds` 在 PR、main/master 推送或手动触发时运行，只有仓库读取权限；不使用模型密钥。

| Runner | 原生架构 | 产物 |
| --- | --- | --- |
| windows-2022 | x86_64 | NSIS .exe |
| ubuntu-22.04 | x86_64 | .deb |
| macos-14 | arm64 | .dmg |

各平台原生构建，不把 Windows Python 冻结产物用于 macOS/Linux，也不生成 universal macOS 包。Runner 版本不是应用最低支持系统的承诺。

## 本地操作

安装 Python 3.12、Node 22、pnpm 10、Rust stable 及 [Tauri 平台依赖](https://v2.tauri.app/start/prerequisites/)。项目内创建 `.venv`，激活后执行：

```text
python -m pip install -e "./backend[dev]"
pnpm install --frozen-lockfile
python scripts/build_sidecar.py
```

Windows PowerShell 可不激活，使用 `.\.venv\Scripts\python.exe` 和 `pnpm.cmd`。确认 `rustc`、`cargo` 在 PATH 中。

按平台选择一条：

```text
pnpm exec tauri build --config src-tauri/tauri.bundle.conf.json --bundles nsis -- --locked
pnpm exec tauri build --config src-tauri/tauri.bundle.conf.json --bundles deb -- --locked
pnpm exec tauri build --config src-tauri/tauri.bundle.conf.json --bundles dmg -- --locked
```

产物位于 `src-tauri/target/release/bundle/`。必须使用上述发布配置，普通 `tauri build` 不装入 Sidecar；`tauri dev` 不需要冻结 Python，保持原启动方式。

## Python 装配

`build_sidecar.py` 用当前虚拟环境中的 PyInstaller 生成单文件程序，包含 Alembic 配置/迁移和动态导入依赖。先在临时目录启动两次，验证冻结程序迁移、JSON Lines 查询与重开；成功后复制到 `src-tauri/binaries/wisetodo-sidecar-<host-triple>[.exe]`。命名与配置遵循 [Tauri externalBin 规则](https://v2.tauri.app/develop/sidecar/)，冻结参数见 [PyInstaller 文档](https://pyinstaller.org/en/stable/usage.html)。

开发配置、数据库、密钥和 `.local` 不作为打包资源。Phase 8.4 起随包收集首批 Skill，缺少用户配置时使用内置基础 Skill/Tool；已有用户配置保持优先，不复制用户插件。范围见 docs/web-and-builtin-tools.md。

CI 先运行后端、前端及 Rust 测试，再冻结 Sidecar、离线冒烟、打包，保存 artifact 14 天，不创建 Release。pnpm/Cargo 使用锁文件；Python 目前依赖版本范围、Rust stable 和 Actions 主版本仍可漂移，尚不属于逐字节可重复构建。

## 验收边界

2026-09-10 本地验证：Windows x64 PyInstaller 冻结和临时库冒烟通过，release 目录中的 Sidecar 再次冒烟通过；Tauri release 编译、前端生产构建及 NSIS 安装包生成通过。新增 5 项构建配置/冒烟校验测试与 Ruff 通过。产物为 `src-tauri/target/release/bundle/nsis/WiseTodo_0.1.0_x64-setup.exe`，尚未执行安装或启动验收。首次 NSIS 下载需要网络权限；Cargo 的 `--offline` 不会禁止打包器下载工具。

三平台首次 CI 运行和安装后验收仍必须完成：安装/卸载、Sidecar 定位、数据库升级、托盘、凭据存储、PDF 子进程及 Skill/Tool 加载。冻结启动冒烟不代表真实模型或所有动态依赖路径均验证通过。

未配置 Windows 签名、macOS Developer ID/公证；系统可能提示未知发布者或拦截。不要把本流程产物标为已签名正式版本。GitHub 上运行 CI、签名和正式发布由维护者操作。
