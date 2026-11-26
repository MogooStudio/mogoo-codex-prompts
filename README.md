# Mogoo 常用提示词

在 Codex 聊天右侧打开「Mogoo 常用提示词」，或在已加载插件的聊天中输入「打开常用提示词面板」。点击条目后，宿主将正文追加到当前草稿，由你编辑和发送。

## 使用

- 在「快速收藏」粘贴正文。标题留空时取首个非空行，分类可直接新建。
- 首页显示收藏。用分类或标题、正文搜索找回其他条目。每条右下角的更多菜单支持编辑、改分类、复制和切换收藏。
- 在「管理分类」中改名或调整顺序。「最近使用」按成功填入的时间排序。
- 点击标题旁的外观按钮，选择跟随 Codex、浅色或深色。所有聊天共享收藏和外观。
- 草稿在 Codex 自己的输入框内编辑。宿主只提供写入时，快速收藏可粘贴正文；未提供写入能力时，面板显示「复制」。

## Windows 本地安装

在本项目根目录执行，机器需要 Python 3.10+ 和 Codex CLI。

```powershell
codex plugin marketplace add .
codex plugin add mogoo-codex-prompts@mogoo-prompts-local
codex plugin list --marketplace mogoo-prompts-local --json
```

如果安装前已打开的聊天没有插件入口，可在新聊天中打开面板。Windows 启动器和源码位于 `plugin/scripts/`。默认数据文件为 Codex 用户目录下的 `mogoo-codex-prompts/prompts.sqlite3`，与插件安装缓存分开。测试可指定 `MOGOO_PROMPTS_DATA` 指向临时目录。

`design/native-list.html` 是独立设计原型。安装版资源来自 `plugin/panel.html` 和 `plugin/panel.js`，由 `plugin/server.py` 通过 MCP 提供。
