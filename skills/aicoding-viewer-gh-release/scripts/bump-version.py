#!/usr/bin/env python3
"""更新当前仓库的 FastAPI 版本号。"""

from __future__ import annotations

import argparse
import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[3]
APP_PY = ROOT / "app.py"


def parse_version(raw_version: str) -> tuple[int, int, int]:
    """校验纯数字语义版本，禁止预发布后缀。"""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(raw_version).strip())
    if not match:
        raise ValueError(f"版本号必须是纯数字 x.y.z，当前值: {raw_version}")
    return tuple(int(part) for part in match.groups())


def read_current_version(content: str) -> str:
    """提取 app.py 当前版本号。"""
    match = re.search(r'FastAPI\([\s\S]*?version="(\d+\.\d+\.\d+)"', content)
    if not match:
        raise RuntimeError("未在 app.py 中找到 FastAPI 版本号")
    return match.group(1)


def bump_version(current_version: str, release_type: str) -> str:
    """根据 bump 类型计算下一个版本号。"""
    major, minor, patch = parse_version(current_version)
    if release_type == "major":
        return f"{major + 1}.0.0"
    if release_type == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_next_version(next_version: str, dry_run: bool) -> dict[str, object]:
    """更新 app.py 中的版本号，并返回变更摘要。"""
    parse_version(next_version)
    content = APP_PY.read_text(encoding="utf-8")
    current_version = read_current_version(content)
    next_content, replacements = re.subn(
        r'(FastAPI\([\s\S]*?version=")(\d+\.\d+\.\d+)(")',
        lambda match: f"{match.group(1)}{next_version}{match.group(3)}",
        content,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("更新 app.py 版本号失败")
    if not dry_run:
        APP_PY.write_text(next_content, encoding="utf-8")
    return {
        "previousVersion": current_version,
        "nextVersion": next_version,
        "dryRun": dry_run,
    }


def parse_args() -> argparse.Namespace:
    """解析命令行参数，支持 patch/minor/major 和显式版本设置。"""
    parser = argparse.ArgumentParser(description="更新 app.py 中的 FastAPI 版本号")
    parser.add_argument("release_type", nargs="?", choices=["major", "minor", "patch"], default="patch")
    parser.add_argument("--set", dest="explicit_version")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    """主入口：输出旧版本与新版本，便于 release 流程复用。"""
    args = parse_args()
    content = APP_PY.read_text(encoding="utf-8")
    current_version = read_current_version(content)
    next_version = args.explicit_version or bump_version(current_version, args.release_type)
    result = write_next_version(next_version, args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
