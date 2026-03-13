---
name: aicoding-viewer-gh-release
description: Use when syncing this 21aicoding-viewer repo to GitHub without GitHub Releases. The skill keeps the public branch aligned with GitHub and explicitly avoids release/tag assets.
---

# AI Coding Viewer GitHub Sync

## 概览

这个 skill 保留旧目录名只是为了兼容历史记录；当前仓库已经停止使用 GitHub Release。
它现在只服务于当前仓库的 GitHub 同步流程，目标是把「公开分支校验、远端同步、误发 release/tag 清理」固定成一条可复用流程，避免后续再次把 release 当成标准交付方式。

## 何时使用

- 需要把当前仓库的公开工作树同步到 GitHub
- 需要校验 GitHub 上的公开分支是否与本地公开分支一致
- 需要清理之前误发的 GitHub Release、tag 或运行包资产

不要用于：

- 创建 GitHub Release
- 构建发布 ZIP
- 递增版本号或维护“版本发布节奏”

## 硬约束

1. **当前仓库不再创建 GitHub Release。**
2. **当前仓库不再生成运行包 ZIP，也不再依赖 tag 作为对外发布手段。**
3. **任何 `.pen` 原型文件都属于私有设计资产，不允许进入 GitHub 仓库历史。**
4. **公开同步只针对公开工作树分支，不要直接推本地私有开发历史。**
5. **如果 GitHub 上已经存在误发的 release/tag，必须先删除，再继续同步代码。**

## 固定流程

### 1. 校验公开工作树状态

先运行：

```bash
git status --short
git branch --show-current
git remote -v
```

必须确认：

- 当前分支是公开工作树分支
- 工作区没有未决冲突
- 远端仓库已经绑定到正确的 GitHub 仓库

### 2. 清理误发的 release 和 tag

先确认 GitHub CLI：

```bash
gh auth status
```

如果 GitHub 上已经存在误发的 release 或 tag，先执行：

```bash
gh release delete <tag> --yes
git push origin :refs/tags/<tag>
git tag -d <tag>
```

如果本地没有这个 tag，`git tag -d` 可以跳过。

### 3. 提交并同步公开分支

```bash
git status --short
git add README.md static/index.html skills/aicoding-viewer-gh-release
git commit -m "<中文提交信息>"
git push origin public-main:main
```

如果公开分支名称不是 `public-main`，按实际分支名替换。

### 4. 同步后校验

```bash
gh repo view banshanshenlou/ai-coding-session-viewer --json name,url,defaultBranchRef
git ls-remote --heads origin
gh release list
```

必须确认：

- GitHub 默认分支仍然是公开分支对应的 `main`
- 远端 head 已经更新到本次提交
- `gh release list` 中不再出现当前仓库的误发 release

## 常见失误

- **继续沿用 release 心智**：这个仓库已经改为“代码同步”，不是“发版分发”
- **直接推本地私有主线**：必须通过公开工作树同步，避免把 `.pen` 和私有历史带上去
- **删了 release 但没删 tag**：GitHub 页面仍会残留旧版本痕迹
- **README 和 skill 口径不一致**：后续很容易再次误发 release
