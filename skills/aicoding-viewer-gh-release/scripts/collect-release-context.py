#!/usr/bin/env python3
"""收集当前仓库的 GitHub Release 上下文。"""

from __future__ import annotations

import json
import locale
import pathlib
import re
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[3]
APP_PY = ROOT / "app.py"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def decode_output(raw: bytes) -> str:
    """兼容 Git 在 Windows 上的不同输出编码，避免 commit 标题变成乱码。"""
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run_git(args: list[str], required: bool = False, error_message: str | None = None) -> str:
    """统一执行 git 命令，并在必要时保留失败上下文。"""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return decode_output(completed.stdout).strip()
    except subprocess.CalledProcessError as exc:
        if not required:
            return ""
        stderr = decode_output(exc.stderr or b"").strip()
        detail = f": {stderr}" if stderr else ""
        raise RuntimeError(error_message or f"git {' '.join(args)} 执行失败{detail}") from exc


def read_version() -> str:
    """从 app.py 中提取 FastAPI 版本号，保证发布口径唯一。"""
    content = APP_PY.read_text(encoding="utf-8")
    match = re.search(r'FastAPI\([\s\S]*?version="(\d+\.\d+\.\d+)"', content)
    if not match:
        raise RuntimeError("未在 app.py 中找到 FastAPI 版本号")
    return match.group(1)


def refresh_tags() -> None:
    """release notes 依赖 tag 范围，必须先刷新远端标签。"""
    run_git(
        ["fetch", "--tags", "--force"],
        required=True,
        error_message="刷新远端 tags 失败，请先确认 git 远端、网络与权限状态",
    )


def list_remotes() -> list[str]:
    """读取当前仓库远端列表，用于区分首次发布和常规发布。"""
    raw = run_git(["remote"])
    return [item for item in raw.splitlines() if item.strip()]


def read_commits(commit_range: str) -> list[dict[str, str]]:
    """把 git log 解析成结构化 commit 列表，供 release notes 归纳使用。"""
    raw = run_git(["log", commit_range, "--pretty=format:%H%x09%s"])
    if not raw:
        return []
    commits: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        commit_hash, _, subject = line.partition("\t")
        commits.append({"hash": commit_hash, "subject": subject})
    return commits


def collect_context() -> dict[str, Any]:
    """组装本次 release 所需的关键上下文。"""
    version = read_version()
    remotes = list_remotes()
    tags_refreshed = False
    if remotes:
        refresh_tags()
        tags_refreshed = True
    latest_tag = run_git(["describe", "--tags", "--abbrev=0"])
    branch = run_git(["branch", "--show-current"])
    status = run_git(["status", "--short"])
    commit_range = f"{latest_tag}..HEAD" if latest_tag else "HEAD"
    diff_stat = run_git(["diff", "--stat", commit_range]) if latest_tag else ""
    changed_files_raw = run_git(["diff", "--name-only", commit_range]) if latest_tag else run_git(["ls-files"])
    changed_files = [item for item in changed_files_raw.splitlines() if item.strip()]

    return {
        "version": version,
        "latestTag": latest_tag,
        "remotes": remotes,
        "remoteConfigured": bool(remotes),
        "tagsRefreshed": tags_refreshed,
        "branch": branch,
        "hasUncommittedChanges": bool(status),
        "gitStatus": status,
        "commitRange": commit_range,
        "commits": read_commits(commit_range),
        "changedFiles": changed_files,
        "diffStat": diff_stat,
        "expectedAssets": {
            "runtimeZip": f"dist/ai-coding-session-viewer-v{version}.zip",
            "notes": f"dist/release-notes-v{version}.md",
        },
        "releaseStyle": {
            "format": "版本 vX.Y.Z + 3~4 句 prose 段落 + 发布资产说明",
            "notesTemplate": "skills/aicoding-viewer-gh-release/templates/release-notes.md",
            "privateAssetsExcluded": ["*.pen"],
        },
    }


def main() -> None:
    """输出 JSON，供后续起草 release notes 与发版复用。"""
    print(json.dumps(collect_context(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
