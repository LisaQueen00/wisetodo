# 0.1.0 发布准备

当前是测试版本准备，不是正式发布公告。Phase 8 已集成桌面体验、主题及默认资料读取链路，实际能力和验收边界见 [集成交付说明](phase8-delivery.md)。保留 package.json、Tauri、Cargo、Python 的 0.1.0，Cargo.lock 同步检查；不自动创建 Git 标签或 GitHub Release。

## 版本与校验文件

项目根目录执行（Windows 用 `.\.venv\Scripts\python.exe`）：

```text
python scripts/prepare_release.py
python scripts/prepare_release.py --artifact src-tauri/target/phase8-final/release/bundle/nsis/WiseTodo_0.1.0_x64-setup.exe
```

第一条只检查版本；第二条针对已构建安装包，在同目录生成 `<安装包名>.sha256`。不修改安装包、不生成签名、不证明安装包内容的版本或来源。SHA-256 用于完整性核对，不代表发布者身份认证。

macOS/Linux 将参数替换为对应 `.dmg`/`.deb` 文件。更新版本时同步四个 manifest 和 Cargo.lock 中本项目条目，重新构建，不可只重命名旧包。脚本不会替维护者决定版本号。

## 发布前人工关卡

- [ ] 确定项目 LICENSE，审查随包第三方依赖许可及所需声明；不得把没有 LICENSE 的仓库描述为已获开源使用授权。
- [ ] 审查并提交代码，确认发布来源 commit；运行三平台 CI，确认日志与 artifact 对应同一提交。
- [ ] 在干净设备上安装、启动、退出、升级与卸载，验收 Sidecar、托盘、持久化、凭据与 PDF 功能。
- [ ] 完成桌面性能/内存验收，确定最低支持系统与目标架构。
- [ ] 核对 Skill/Tool 初次安装与覆盖行为：缺少配置启用内置 12 工具及三份 Skill；用户配置完整覆盖，空配置可禁用，示例外部 MCP 服务不会自动启动。
- [ ] 决定签名/公证；若为未签名测试包，发布页明确系统警告和测试用途。
- [ ] 按需人工验证模型业务效果；不默认重复消耗模型 Token。
- [ ] 更新 CHANGELOG 的实际发布日期、已知限制；确认版本与包名，生成并核对 SHA-256。
- [ ] 维护者自行决定标签及 GitHub Release（当前建议预发布），上传安装包和对应校验文件。

不要上传 `.local`、虚拟环境、用户数据库、凭据、模型配置或整个工作区。CI 只上传 bundle 目录；本流程没有发布权限、发布密钥或自动推送步骤。

## 当前本地交付物

Windows x64 集成版：`src-tauri/target/phase8-final/release/bundle/nsis/WiseTodo_0.1.0_x64-setup.exe`；直接运行版位于该 target 的 `release/wisetodo.exe`，需保留同目录 Sidecar。此前阶段路径是历史构建记录，部分已经清理。标准构建未指定 CARGO_TARGET_DIR 时仍输出 target/release。构建详情见 [building.md](building.md)。目录已被 Git 忽略；无需将二进制或校验文件提交到源码仓库。本地准备完成不代表上述人工关卡通过。
