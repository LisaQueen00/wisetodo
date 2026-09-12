# 三平台构建

本流程生成未签名测试安装包，不自动发布版本。GitHub Actions 的 `Desktop builds` 在 PR、main/master 推送或手动触发时运行，只有仓库读取权限；不使用模型密钥。

| Runner | 原生架构 | 产物 |
| --- | --- | --- |
| windows-2022 | x86_64 | NSIS .exe |
| ubuntu-22.04 | x86_64 | .deb |
| macos-14 | arm64 | .dmg |

各平台原生构建，不把 Windows Python 冻结产物用于 macOS/Linux，也不生成 universal macOS 包。Runner 版本不是应用最低支持系统的承诺。

## 本地操作

普通用户只需安装或解压运行，见 [安装与打开说明](getting-started.md)。下文面向构建者。三平台使用同一个 `scripts/build_release.py`，自动选择本机的 NSIS/DMG/DEB，串联冻结 Sidecar、Tauri 打包、临时配置验收和校验文件；Windows 额外生成双 EXE 的直接运行 ZIP（不是便携数据模式）。不会自动安装、上传、发布或调用模型。

### Windows PowerShell

先安装 Microsoft C++ Build Tools（桌面 C++ 工作负载）、WebView2、Python 3.12、Node 22、pnpm 10 和 Rust stable。项目根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "./backend[dev]"
pnpm.cmd install --frozen-lockfile
.\.venv\Scripts\python.exe scripts/build_release.py
```

已经存在 `.venv` 时不必重建。若 cargo/rustc 未找到，重开终端并检查 PATH。已有构建的 EXE 正在运行时先从托盘退出，否则链接可能失败。

### macOS

准备 Xcode Command Line Tools（`xcode-select --install`）、Python 3.12、Node 22、pnpm 10 和 Rust stable。Python 与 Rust 必须使用相同架构，不要混用 Rosetta x64 和 arm64。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
pnpm install --frozen-lockfile
.venv/bin/python scripts/build_release.py
```

输出 `.dmg` 及 `bundle/macos/WiseTodo.app`；仅构建当前原生架构，没有合并 universal。签名、公证不在默认脚本中自动配置。

### Linux（Ubuntu 22.04 构建环境）

准备 Python 3.12、Node 22、pnpm 10、Rust stable，并按发行版安装平台依赖。Ubuntu 22.04 的默认 Python 不是 3.12，需自行准备匹配版本；不要覆盖系统 Python。

```bash
sudo apt-get update
sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev librsvg2-dev libayatana-appindicator3-dev patchelf
python3.12 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
pnpm install --frozen-lockfile
.venv/bin/python scripts/build_release.py
```

需要桌面图形会话和系统凭据服务才能做安装后的交互验收。构建通过不代表无头服务器可运行桌面窗口。平台依赖以 [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) 为准。

### 输出与调试

默认输出 `src-tauri/target/release/bundle/{nsis,dmg,deb}`（仅本机对应目录），Windows 直接运行 ZIP 位于 `bundle/direct-run`；所有分发包旁有 `.sha256`。若设置 `CARGO_TARGET_DIR`，输出改到其 `release/bundle`。未锁定 Python 全部依赖，不保证逐字节可重复构建。

可选 `--cargo-offline` 只禁止 Cargo 获取新依赖，不禁止 PyInstaller/Tauri 打包工具需要的联网。第一次构建通常需要网络。脚本不自动运行全部源码测试，交付前另运行测试或依赖 CI 的测试步骤。

开发调试：安装依赖后执行 `pnpm.cmd tauri dev`（Windows）或 `pnpm tauri dev`（macOS/Linux），不需要提前冻结 Sidecar；普通 `pnpm dev` 只有浏览器前端，不等于完整桌面应用。

### GitHub Actions 三端打包

提交并推送代码后，进入 Actions → Desktop builds → Run workflow，选择分支；或者使用现有 PR/main/master 触发。三个 job 分别进行原生测试和统一打包。完成后下载 `wisetodo-windows-2022`、`wisetodo-ubuntu-22.04`、`wisetodo-macos-14` artifact（保存 14 天）。失败 job 没有可用包时应先检查日志，不使用其他架构的 Sidecar 替代。

维护者负责触发远端流水线和审查结果；本地 Windows 会话不会替你创建 Release。首次 macOS/Linux CI 和安装验证尚待执行。

## 分步命令（排障参考）

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
