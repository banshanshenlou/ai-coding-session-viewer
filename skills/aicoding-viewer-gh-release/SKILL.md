---
name: aicoding-viewer-gh-release
description: Use when releasing this 21aicoding-viewer repo to GitHub from the current workspace, including bumping the FastAPI version in app.py, drafting release notes from commits since the last tag, building the runtime ZIP bundle, and publishing the release with gh.
---

# AI Coding Viewer GitHub Release

## 概览

这个 skill 只服务于当前仓库的发布流程，目标是把「版本号、运行包、release notes、GitHub Release 校验」固定成一条可复用流水线，避免仓库名、资产名和说明文风在每次发布时漂移。

## 何时使用

- 需要把当前仓库推到 GitHub 并准备发正式 release
- 需要根据“最近一个 tag 到当前 HEAD”的 commit / diff 归纳 release notes
- 需要生成可直接下载的运行包，而不是只依赖 GitHub 自动源码包

不要用于：

- 只做本地开发验证
- 只改 README 或原型，不准备发版
- 只想打临时 tag，不创建 GitHub Release

## 硬约束

1. **版本号只以 `app.py` 中 `FastAPI(... version="x.y.z")` 为准**，不要另造 `package.json` 或额外版本文件。
2. **发布资产固定为 1 个主包**：运行包 ZIP。GitHub 自动生成的源码包不算主资产。
3. **release notes 必须是短段落 prose 风格**，不要写成 commit 清单堆砌。
4. **如果仓库已配置远端，发布前必须先同步远端 tags**；如果当前还没有远端，则按首次发布场景处理，并在 release notes 草稿里明确这是首个远端 release。
5. **发布前必须跑最小验证链**：`py_compile`、发布上下文采集、打包脚本 dry-run / 实跑。
6. **运行包必须包含 README、启动脚本、后端入口、静态资源与依赖文件**，不能只传源码快照。
7. **任何 `.pen` 原型文件都属于私有设计资产，不允许进入 GitHub Release 资产列表。**

## 产物命名

- 运行包：`dist/ai-coding-session-viewer-v<version>.zip`
- Release notes 草稿：`dist/release-notes-v<version>.md`

## 固定流程

### 1. 收集发布上下文

先运行：

```bash
python skills/aicoding-viewer-gh-release/scripts/collect-release-context.py
```

必须检查输出中的：

- 当前版本
- 最近一个 tag
- 当前分支
- 工作区是否干净
- commit 范围
- 变更文件列表
- 预计生成的资产名

如果远端 tags 同步失败、工作区混入无关改动、或者当前仓库还没有准备好 README，不要继续。
如果当前没有远端，则先允许生成本地 release 上下文、版本号和打包资产；真正创建 GitHub Release 前再补远端并重新执行一次上下文采集。

### 2. 起草 release notes

读取模板：

```text
skills/aicoding-viewer-gh-release/templates/release-notes.md
```

要求：

- 第一行固定为 `版本 v<version>`
- 用 3 到 4 句完整短段落概括本次发布
- 只写用户可感知的改动，不写调试过程
- 结尾保留“发布资产说明”段落

保存到：

```text
dist/release-notes-v<version>.md
```

### 3. 递增版本号

默认递增 `patch`：

```bash
python skills/aicoding-viewer-gh-release/scripts/bump-version.py patch
```

显式设置版本：

```bash
python skills/aicoding-viewer-gh-release/scripts/bump-version.py --set 2.1.0
```

只预览不落盘：

```bash
python skills/aicoding-viewer-gh-release/scripts/bump-version.py patch --dry-run
```

### 4. 运行最小验证链

```bash
python -m py_compile app.py
python -m py_compile skills/aicoding-viewer-gh-release/scripts/collect-release-context.py
python -m py_compile skills/aicoding-viewer-gh-release/scripts/bump-version.py
python -m py_compile skills/aicoding-viewer-gh-release/scripts/build-release-bundles.py
python skills/aicoding-viewer-gh-release/scripts/build-release-bundles.py --dry-run
```

### 5. 构建发布资产

```bash
python skills/aicoding-viewer-gh-release/scripts/build-release-bundles.py
```

这个脚本会：

- 打包运行包 ZIP
- 自动创建 `dist/`
- 只收录当前仓库约定的发布文件
- 自动排除本地私有设计稿

### 6. 提交、打 tag、创建 release

先确认 GitHub CLI：

```bash
gh auth status
```

然后执行：

```bash
git status --short
git add README.md app.py skills/aicoding-viewer-gh-release
git commit -m "<中文发布提交信息>"
git push
git tag v<version>
git push origin v<version>
gh release create v<version> \
  dist/ai-coding-session-viewer-v<version>.zip \
  -t "v<version>" \
  -F dist/release-notes-v<version>.md
```

### 7. 发布后校验

```bash
gh release view v<version> --json tagName,name,body,assets,publishedAt
```

必须确认：

- tag 为 `v<version>`
- 标题为 `v<version>`
- body 与本地草稿一致
- assets 中只包含运行包 ZIP

## 文风基线

release notes 推荐保持下面这种结构：

```text
版本 v2.x.y

本次更新围绕……
本次更新补齐了……
本次更新优化了……

发布资产说明
运行包：ai-coding-session-viewer-v2.x.y.zip
```

禁止：

- 直接粘贴 commit 标题
- 写成流水账
- 混入“刚刚”“顺手”“临时处理”这类过程化口吻

## 常见失误

- **只上传 GitHub 自动源码包**：这不等于可直接运行的发布资产
- **忘了带 README 和启动脚本**：运行包会失去开箱体验
- **手工改错版本号**：必须走 `bump-version.py`
- **release notes 没基于 tag 范围归纳**：会把历史发布内容重复写进去
- **把原型文件混进 GitHub 资产**：设计稿是本地私有资产，必须留在仓库本地
