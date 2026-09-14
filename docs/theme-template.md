# 完整主题模板

下载或保存同目录的 [theme-v2.full.json](theme-v2.full.json)，在「主题设置」导入、预览后保存。
它展开当前 47 个组件的所有合法状态、所有支持的样式字段及 7 个文字属性。
这是方便改色的深色示例，不是默认主题的逐像素复制；不会改变内置默认值。

## 修改顺序

1. 修改 `name`，避免覆盖自己的其他主题。
2. 优先调整 `palette`：`window` 窗口、`surface` 卡片、`control` 控件、`text` 正文、`muted` 次要文字、`accent` 强调色、`high` 高优先级。引用这些颜色的组件一起响应。
3. 要单独修改组件，调整 `components` 对应状态；如 `todoCard.default.background` 可以从 `{"ref":"surface"}` 改成 `"#243244"`。
4. `default` 是常态，`hover` 悬停、`active` 按下、`focus` 焦点、`disabled` 禁用、`selected` 选中、`completed` 完成。模板已经列出每个组件允许的状态，不要给它新增不支持的状态。

由于模板显式覆盖所有状态，只改 `default` 不会同步覆盖已有的 `hover` 等配置；想统一修改应改共享 palette，或删除不需要单独定制的状态。
`components` 优先于基础 `colors`；如果修改 `colors` 没反应，请调整覆盖它的组件字段。

## 文字与渐变

`typography` 包含 `fontFamily`（system 或已安装字体）、`fontSize`、`fontWeight`（400 正常、700 加粗）、`fontStyle`（normal/italic）、`lineHeight`、`letterSpacing`、`textDecoration`（none/underline/line-through）。
模板逐组件显式设定文字，因此全局字体修改也可能被具体组件覆盖；删除局部 typography 即可恢复继承。

窗口已有线性渐变示例。其他支持 background 的组件也可使用：

```json
{"type":"linear","angle":135,"stops":[{"color":"#82CFFF","position":0},{"color":"#F4B9D1","position":100}]}
```

径向渐变改为 `"type":"radial"` 并删除 angle。位置按 0–100 升序，至少两个色标。
颜色为 #RRGGBB 或 #RRGGBBAA；窗口基础 `colors.window.background` 只允许六位。
窗口和装饰底色仍受桌面透明度调节影响，文字不整体变透明。

## 注意

- JSON 不支持注释、尾逗号；不能添加 description、$schema 等未支持的字段。
- 不能增加圆角、间距、图片 URL 或任意 CSS；模板只覆盖现有主题能力。
- 状态存在不代表每个元素都能交互，例如静态文字通常不会获得焦点。
- 边框/阴影字段设置颜色，不增加任意几何样式；安全恢复按钮故意不跟随主题。
- 导入上限 64 KiB。模板约 49 KiB，每个状态在一行是为保留完整字段又不超限；全量自动格式化为多行可能超限。
- 修改组件目录后，维护者运行 `node scripts/build_theme_template.mjs` 重新生成模板；测试会校验覆盖范围与真实导入逻辑。
