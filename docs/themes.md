# WiseTodo 主题

顶部“主题设置”打开编辑弹窗。默认使用既有深紫色系，不要求用户接受新配色。修改立即预览；取消/Escape 恢复之前主题，保存才写入本机。内置默认不能覆盖，先“复制为自定义主题”或更名。相同自定义名称保存会更新该主题；最多保存 20 个。设置弹窗与入口跟随主题：弹窗复用 modelSettings 组件，按钮/输入沿用现有映射。仅“安全恢复默认配色”按钮固定高对比并吸顶显示，点击恢复预览，保存才留存。

## 可读 JSON

### v2 组件级主题

当前导出版本为 2，旧版 1 导入自动升级。JSON Schema 位于 [theme-v2.schema.json](theme-v2.schema.json)，可在编辑器中关联该文件获得字段说明和补全；主题 JSON 本身不接受 `$schema` 字段。Schema 由 `node scripts/build_theme_schema.mjs` 从组件目录生成，运行时额外检查色板引用、字体字符与渐变排序。

```json
{
  "schemaVersion": 2,
  "name": "暮色阅读",
  "palette": { "ink": "#F3EDF8", "accent": "#B99AE8" },
  "components": {
    "global": { "default": { "typography": { "fontFamily": "system", "lineHeight": 1.5 } } },
    "todoCard": {
      "default": {
        "background": { "type": "linear", "angle": 135, "stops": [
          { "color": "#292338", "position": 0 },
          { "color": "#171722", "position": 100 }
        ] },
        "border": { "ref": "accent" }
      },
      "hover": { "border": "#DEC3FF" }
    },
    "todoTitle": { "default": { "text": { "ref": "ink" }, "typography": { "fontWeight": 700, "fontStyle": "italic" } } },
    "todoItemText": { "completed": { "text": "#9EB4A5", "typography": { "textDecoration": "line-through" } } }
  }
}
```

“组件精细样式 · v2”可选择组件与状态，配置纯色、线性/径向渐变（2–12 个色标）、字号 8–48px、字重 100–900、斜体、行高 0.8–3、字间距 -2–10px 与文字装饰。颜色文本在离开输入框时校验应用；数字和选择项直接预览。高级 JSON 区可编辑 palette 和 components，需点击“校验并预览”。重置当前状态恢复继承。

覆盖窗口/顶栏/标题、Todo 卡片/标题/子项/序号/优先级/进度、三类消息/角色/正文/附件/历史/执行阶段、模型设置、按钮/输入/下拉菜单/提示与滚动条。各组件实际选择器、可用状态和字段列于 Schema 与设置界面，未公开的状态不接受导入。

基础 colors 保留作为兼容默认层；global 只开放文字和排版，显式组件覆盖优先于全局。缺省组件字段不创建覆盖，状态字段未填写时使用基础状态。背景支持渐变，文字/边框/阴影颜色只支持纯色或色板引用。阴影几何固定为 0 4px 16px；不是任意 CSS 编辑器，不开放 URL、脚本或外部字体加载。

窗口 v2 背景仍与桌面不透明度叠加。装饰性组件背景（含各状态的纯色、线性/径向渐变）使用分层淡化：滑块 60–100% 对应装饰背景系数 0–1，窗口底色仍为 0.6–1。这样在最低档不会由多层不透明卡片遮住桌面；中间档仍存在正常背景合成，因此该数值不是最终每个像素的透明度。100% 保留主题原有 alpha。文字、图标不施加整层 opacity；按钮、输入框、下拉菜单、模型设置、进度条和滚动条背景保持原主题值以保证可读性。

checkbox/slider 使用原生控件，仅开放 accent；进度与滚动条开放背景；序号和 placeholder 仅开放文字/排版。安全恢复按钮、系统标题栏及文件对话框不参与组件主题。父容器文字不保证覆盖子元素自己的颜色，请使用 todoTitle/messageText 等细分字段。圆角、点击区域、指针和动画使用统一默认规则，不增加 Schema 字段。自动测试不是像素级或跨平台实机验收。

### 兼容旧版基础色板

```json
{
  "schemaVersion": 1,
  "name": "我的阅读主题",
  "font": { "family": "system", "sizePx": 16 },
  "colors": {
    "text": { "primary": "#f4eef9", "secondary": "#ffffff99" },
    "dropdown": {
      "background": "#211a2b",
      "text": "#f4eef9",
      "itemHoverBackground": "#ffffff26",
      "itemSelectedBackground": "#a881d833",
      "itemSelectedText": "#ffffff"
    }
  }
}
```

导入允许省略 font/colors 内字段，缺省取内置默认，不取上一个主题。导出包含完整基础色板及已配置组件覆盖，使用两空格缩进和换行；未覆盖组件的可用字段请查阅 Schema。标准 JSON 不含注释；未知字段直接报错。文件最大 64 KiB，支持版本 1 和 2；纯色为 #RRGGBB 或 #RRGGBBAA，最后两位是 alpha。旧 colors.window.background 只允许六位颜色。

| 分组 | 字段 |
| --- | --- |
| text | primary、secondary、muted：正文/次要/辅助文字 |
| window | background、header：面板底色/顶部叠加底色 |
| todo | background、border、priorityHigh、priorityNormal、completedText、completedBackground |
| chat | background、messageBackground：聊天区/消息及辅助容器 |
| settings | background：模型设置编辑区 |
| border | normal：通用边框，也用于滚动条 |
| button | background、text、hoverBackground、primaryBackground、primaryText、disabledText |
| input | background、text、placeholder、border |
| dropdown | background、text、itemHoverBackground、itemSelectedBackground、itemSelectedText |
| status | error、success、warning、focus、highlight、progressTrack |

主题是纯数据，不接受任意 CSS、脚本、URL 或远程字体。font.family 使用 system 或本机字体名称（例如 Microsoft YaHei、Arial），缺失时由浏览器回退系统字体。sizePx 范围 12–20，是基础 rem 字号，会按比例影响现有 rem 布局。默认 16px。JSON 不携带字体文件，没有导入字体资源或自动下载行为。

三个业务下拉框使用应用内 listbox，菜单颜色可控。支持方向键、Home/End、Enter/空格、Escape、首字母定位和鼠标选择；长列表内部滚动。不是操作系统菜单，不保证系统标题栏或文件选择器能随主题变化。

## 留存与边界

WebView localStorage 中 `wisetodo.themes.v1` 保存自定义主题和当前选择。配置损坏/无法读取时使用默认但不自动覆盖原记录；写入失败提示并停留预览，可以导出后取消。新装/清除站点数据后恢复默认；模型配置、API Key、聊天和背景不透明度不进入主题 JSON。

导入文件先校验再预览，不自动保存，也不监听外部文件变化。桌面端导出打开原生“另存为”，默认文件名 `wisetodo-theme.json`；只写用户在对话框选择的文件，写入并同步成功后显示路径。取消不报错，写入失败显示错误且可重试，处理中禁止重复点击。浏览器预览仍使用下载链接，只提示已请求下载，不声称已落盘。不替用户上传或发布。

原生对话框采用 [rfd AsyncFileDialog](https://docs.rs/rfd/0.15.4/rfd/struct.AsyncFileDialog.html)，绑定父窗口。自动测试覆盖导出内容、等待写入、取消、失败、重试与 Rust 文件写入；真实 Windows 保存对话框、覆盖确认、重新导入，以及颜色对比度、字体回退和系统高缩放仍需人工验收。对比度提示只检查正文与窗口底色完全相同的明显情况，不是完整无障碍认证。

主题默认统一了之前零散的文字/背景状态值，尽量保留现有色系；不是逐像素复刻每个白色 alpha。安全恢复按钮固定配色是有意保留的例外。
