# 安装、打开与首次使用

当前为 0.1.0 未签名测试版。普通用户无需安装 Python、Node 或 Rust。首次使用模型功能需要自行配置服务；手动 Todo 不需要模型。

## Windows x64

推荐下载 `WiseTodo_0.1.0_x64-setup.exe`，双击按安装向导操作；完成后从开始菜单搜索 WiseTodo 打开。

也可下载 `*-direct-run.zip`，**先完整解压**，再双击其中的 `wisetodo.exe`。不要在 ZIP 预览中启动、不要单独搬走 EXE：同目录 `wisetodo-sidecar.exe` 必须保留。需要 Microsoft Edge WebView2 Runtime；安装版可处理运行时安装，直接运行包需系统已经具备运行时。它不是“数据随文件夹移动”的便携版，数据仍保存在本机应用数据目录。

若提示未知发布者，先核实来源与 SHA256；不要关闭系统安全防护。官方 Windows 打包机制见 [Tauri Windows Installer](https://v2.tauri.app/distribute/windows-installer/)。

## macOS

下载匹配芯片架构的 `.dmg`，打开后将 WiseTodo 拖到 Applications（应用程序），弹出磁盘映像，再从应用程序或 Spotlight 打开。保留整个 `.app`，不要拆出内部主程序或 Sidecar。

当前 CI 目标为 Apple Silicon/arm64，不是 universal 包；Intel 机器需在对应原生环境另行构建。当前没有 Developer ID 签名和公证，Gatekeeper 可能阻止打开；仅在确认来源可信时按系统“隐私与安全性”的指引处理。若系统不允许，不建议通过关闭 Gatekeeper 或移除隔离属性规避，应等待签名版本。

macOS 包须在 macOS Runner/设备生成；Windows 本地目录没有 `.dmg` 并不表示文件被漏传。

## Linux（首版 Debian/Ubuntu 系）

下载 `.deb`，使用发行版软件安装器打开；也可在下载目录运行以下命令，将文件名替换为实际下载文件名：

```bash
sudo apt install ./WiseTodo_0.1.0_amd64.deb
```

安装后从应用菜单打开 WiseTodo，或在终端执行 `wisetodo`。不要只复制 `/usr/bin/wisetodo` 到另一台机器，系统库及 Sidecar 同样必需。Linux 首版只有 `.deb`，没有承诺 AppImage/RPM；Wayland 下置顶、窗口定位和托盘行为可能受桌面环境限制。

需要可用的桌面 Secret Service（例如已解锁的 GNOME Keyring）才能留存 API Key；缺失时会提示失败，不会悄悄改为明文保存。

## 通用操作

1. 首次打开应无个人 Todo 和模型配置。相同用户升级/重新解压时看到以前的数据是正常现象，不表示安装包含有个人数据。
2. 在 Todo 区直接新建/编辑；每个 Todo 至少两个子项。勾选全部子项后顶层完成。
3. 点击“打开 Chat”，在 Settings 配置 Base URL、模型名和 API Key 并保存。测试连接是手动触发，可能产生少量模型费用，不自动重复测试。
4. 可提供项目链接、阅读资料等创建任务。默认资料读取工具无需额外复制配置；已有自定义 Tool/Skill 会覆盖默认内容。
5. 主题设置支持 JSON 导入、预览与保存。背景透明度在“桌面选项”中；贴顶自动隐藏未实现，本版不加入。
6. 关闭窗口通常进入托盘/菜单栏后台；要完全退出，请使用托盘菜单的退出项。程序只允许一个实例，再次启动会唤回已有窗口。
7. 更新前先从托盘彻底退出旧版，再安装或启动新版，避免误以为新版无变化。

数据库、非密钥模型配置等位于系统应用数据目录，密钥单独使用系统凭据库，主题和窗口偏好也在本机留存。不要为“干净测试”删除自己的真实数据。卸载是否保留所有设置仍需各平台实机验收，不承诺通过卸载完成数据清除。

## 获取与校验

尚未正式发布时，维护者可从 GitHub Actions → Desktop builds → 对应成功运行 → Artifacts 下载本平台包。Artifacts 外层 ZIP 是下载容器，先解压才能找到安装包及 `.sha256`。只使用三个 job 都检查过的同一来源提交，不把 Windows 测试通过当作跨平台验收完成。

核对文件摘要：

```powershell
Get-FileHash .\WiseTodo_0.1.0_x64-setup.exe -Algorithm SHA256
```

macOS 使用 `shasum -a 256 文件名.dmg`，Linux 使用 `sha256sum 文件名.deb`，与 `.sha256` 内容比较。校验和验证传输完整性，不代替签名和可信来源确认。

问题反馈请提供系统/架构、版本、操作步骤及脱敏截图；不要发送 API Key、完整个人数据库或包含隐私的模型配置。
