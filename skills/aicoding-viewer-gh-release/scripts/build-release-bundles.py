#!/usr/bin/env python3
"""构建当前仓库的发布 ZIP 资产。"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import zipfile
from typing import Iterable


ROOT = pathlib.Path(__file__).resolve().parents[3]
DIST_DIR = ROOT / "dist"
APP_PY = ROOT / "app.py"

RUNTIME_FILES = [
    "README.md",
    "app.py",
    "requirements.txt",
    "start-viewer.bat",
    "start-viewer.sh",
]

RUNTIME_DIRS = [
    "static",
]


def read_version() -> str:
    """从 app.py 中提取当前版本号，用于统一资产命名。"""
    content = APP_PY.read_text(encoding="utf-8")
    match = re.search(r'FastAPI\([\s\S]*?version="(\d+\.\d+\.\d+)"', content)
    if not match:
        raise RuntimeError("未在 app.py 中找到 FastAPI 版本号")
    return match.group(1)


def iter_existing_files(paths: Iterable[pathlib.Path]) -> list[pathlib.Path]:
    """过滤出实际存在的文件，缺失关键文件时立即失败。"""
    files: list[pathlib.Path] = []
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"缺少发布文件: {path.relative_to(ROOT)}")
        if path.is_file():
            files.append(path)
    return files


def collect_runtime_files() -> list[pathlib.Path]:
    """收集运行包所需的文件列表。"""
    files = iter_existing_files(ROOT / name for name in RUNTIME_FILES)
    for directory_name in RUNTIME_DIRS:
        directory = ROOT / directory_name
        if not directory.exists():
            raise RuntimeError(f"缺少发布目录: {directory_name}")
        files.extend(sorted(path for path in directory.rglob("*") if path.is_file()))
    return files


def write_zip(zip_path: pathlib.Path, files: list[pathlib.Path], dry_run: bool) -> None:
    """以仓库相对路径写入 ZIP，保持下载后的目录结构稳定。"""
    if dry_run:
        return
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=file_path.relative_to(ROOT))


def build_bundles(bundle: str, dry_run: bool) -> dict[str, object]:
    """根据目标类型构建运行包。"""
    version = read_version()
    runtime_zip = DIST_DIR / f"ai-coding-session-viewer-v{version}.zip"

    result: dict[str, object] = {
        "version": version,
        "dryRun": dry_run,
        "bundles": {},
    }

    if bundle in {"runtime", "all"}:
        runtime_files = collect_runtime_files()
        write_zip(runtime_zip, runtime_files, dry_run)
        result["bundles"] = {
            **result["bundles"],
            "runtime": {
                "zipPath": str(runtime_zip.relative_to(ROOT)),
                "fileCount": len(runtime_files),
                "files": [str(path.relative_to(ROOT)) for path in runtime_files],
            },
        }

    return result


def parse_args() -> argparse.Namespace:
    """解析命令行参数，支持指定 bundle 类型与 dry-run。"""
    parser = argparse.ArgumentParser(description="构建 AI Coding Session Viewer 发布 ZIP 资产")
    parser.add_argument("--bundle", choices=["runtime", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    """主入口：输出打包结果 JSON。"""
    args = parse_args()
    print(json.dumps(build_bundles(args.bundle, args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
