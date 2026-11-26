# Mogoo 常用提示词

[插件网站](https://mogoostudio.github.io/mogoo-codex-prompts/)

在 Codex 聊天右侧打开「Mogoo 常用提示词」，或在已加载插件的聊天中输入「打开常用提示词面板」。点击条目后，宿主将正文追加到当前草稿，由你编辑和发送。

## 使用

- 在「快速收藏」粘贴正文。标题留空时取首个非空行，分类可直接新建。
- 首页显示收藏。用分类或标题、正文搜索找回其他条目。每条右下角的更多菜单支持编辑、改分类、复制和切换收藏。
- 在「管理分类」中改名或调整顺序。「最近使用」按成功填入的时间排序。
- 点击标题旁的外观按钮，选择跟随 Codex、浅色或深色。所有聊天共享收藏和外观。
- 在 Codex 输入框内编辑并发送草稿。当前聊天没有草稿写入权限时，可以复制提示词。

## 安装

需要 Python 3.10+、Git 和带有插件命令的 Codex CLI。插件包在本仓库的 `plugin/`，面板从本仓库的 GitHub 标签检查更新。

在终端执行以下命令，再到新聊天中打开「Mogoo 常用提示词」。第一条在 Codex 登记 GitHub 上的 Mogoo 插件市场，第二条安装常用提示词。

```powershell
codex plugin marketplace add https://github.com/MogooStudio/mogoo-codex-plugin.git --ref main --json
codex plugin add mogoo-codex-prompts@mogoo-codex-plugin --json
```

在 `codex plugin list --marketplace mogoo-codex-plugin --json` 中确认新安装已启用。先前从产品独立目录安装的用户，可在新聊天核对原收藏后，通过 `codex plugin remove mogoo-codex-prompts@mogoo-codex-prompts --json` 移除旧安装。使用同名旧市场的用户参见[目录迁移说明](https://github.com/MogooStudio/mogoo-codex-plugin#已登记同名旧目录时)。

## 更新

点击面板底部的版本号可查看版本、立即检查、开关自动检查或忽略某个新版。更新器读取 GitHub 上的稳定版标签 `v主版本.次版本.修订号`，自动检查成功后六小时内复用结果。点击「立即更新」并确认后，插件通过 Codex CLI 安装。新版在新聊天或重启 Codex 后生效。

更新器核对 Codex 登记的 GitHub 地址、发行标签和 `main` 指向，再由 Codex 从 GitHub 拉取 `plugin/` 安装。如果面板显示手动更新命令，可复制到终端执行。

收藏、分类、最近使用和外观保存在 Codex 用户目录下的 `mogoo-codex-prompts/prompts.sqlite3`。更新状态单独保存。测试可用 `MOGOO_PROMPTS_DATA` 指定临时数据目录。

## 维护

改动版本时同步 `plugin/plugin.json`、`plugin/.codex-plugin/plugin.json` 和更新记录。MCP 服务和面板从包内清单读取运行版本。先验证安装和测试，再让 GitHub 的 `main` 与稳定版标签指向同一提交。

```powershell
python -B -m unittest discover -s tests
node --check plugin/panel.js
```

[更新记录](https://github.com/MogooStudio/mogoo-codex-prompts/blob/main/CHANGELOG.zh.md)
