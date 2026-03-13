# AI Coding Session Viewer

面向 OpenCode、Codex、Claude Code 的本地会话查看器。它把分散在不同工具目录下的会话历史统一聚合到一个本地 Web 界面里，提供路径树分组、聊天式阅读、全文搜索、Markdown 导出、恢复命令复制和多数据源切换能力。

## 适用场景

- 想把 OpenCode、Codex、Claude Code 的会话放到同一个界面里查看
- 需要按项目路径快速定位某次对话，而不是在原始目录里手工翻文件
- 需要把单次会话导出成 Markdown，或者复制 `codex resume` / 继续恢复命令
- 需要把 AI 编程过程当作可审查资产保存下来，便于复盘、审阅和分享

## 核心能力

- 同时读取 OpenCode、Codex、Claude Code 三种本地会话数据源
- 左侧按路径目录分组的会话树，支持展开折叠与排序切换
- 中间区域采用聊天阅读布局，适合长会话连续浏览
- 支持会话搜索、代码高亮、主题切换、快速滚动到底部
- 支持单会话导出 Markdown
- 支持复制恢复命令，方便回到原工具继续会话
- 提供 Windows / macOS / Linux 启动脚本

## 支持数据源

| 数据源 | 默认路径 | 可覆盖环境变量 |
| --- | --- | --- |
| OpenCode | `~/.local/share/opencode/opencode.db` 或 Windows LocalAppData | `OPENCODE_DB_PATH` / `OPENCODE_HOME` |
| Codex | `~/.codex/sessions` | `CODEX_SESSIONS_PATH` / `CODEX_HOME` |
| Claude Code | `~/.claude/projects` | `CLAUDE_PROJECTS_PATH` / `CLAUDE_HOME` |

说明：

- 所有路径都会先做环境变量和用户目录展开，再回退到内置默认路径
- 这个项目只读取本地数据，不依赖云端服务

## 快速开始

### 1. 安装依赖

```bash
python -m pip install -r requirements.txt
```

### 2. 启动服务

Windows：

```bat
start-viewer.bat
```

macOS / Linux：

```bash
chmod +x start-viewer.sh
./start-viewer.sh
```

也可以直接运行：

```bash
python app.py
```

默认地址：

```text
http://localhost:8765
```

## 常用环境变量

| 变量名 | 作用 |
| --- | --- |
| `OPENCODE_VIEWER_URL` | 指定自动打开浏览器时展示的地址 |
| `OPENCODE_VIEWER_OPEN_BROWSER` | 设置为 `0` 可关闭自动打开浏览器 |
| `OPENCODE_DB_PATH` | 显式指定 OpenCode 数据库路径 |
| `CODEX_SESSIONS_PATH` | 显式指定 Codex 会话目录 |
| `CLAUDE_PROJECTS_PATH` | 显式指定 Claude Code 项目目录 |

## 项目结构

```text
.
├─ app.py                              # FastAPI 后端，负责聚合三类会话数据源
├─ static/index.html                   # 单文件前端，实现查看器界面与交互
├─ start-viewer.bat                    # Windows 启动脚本
├─ start-viewer.sh                     # macOS / Linux 启动脚本
└─ skills/aicoding-viewer-gh-release/  # GitHub 同步 skill（保留旧目录名，不再创建 release）
```

## GitHub 同步约定

仓库内置了一个面向当前项目的 GitHub 同步 skill：

```text
skills/aicoding-viewer-gh-release
```

它现在只负责约束这类动作：

- 校验公开工作树是否干净
- 把公开分支同步到 GitHub 仓库
- 清理误发的 GitHub Release 和 tag
- 确保 `.pen` 等私有设计资产不进入公开历史

当前仓库不再使用 GitHub Release 流程，不再生成发布 ZIP，不再通过版本 tag 管理对外发布。
设计稿属于本地私有资产，不在 GitHub README、GitHub 仓库历史或任何公开发布资产中暴露。

如果你准备把这个仓库同步到 GitHub，直接维护公开分支并推送即可，不需要额外创建 release。

## 当前定位

这个仓库的重点不是“会话导出脚本”，而是“本地 AI 编程记录的统一阅读器”。它更适合做成一个轻量、可独立运行、便于开源演示的工具仓库。
