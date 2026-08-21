"""Validate and build the AstrBot plugin release archive.

The repository root is the plugin source tree.  This module deliberately uses
only the standard library so CI can validate a release before installing any
runtime dependency.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "astrbot_plugin_marvel_rivals"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
REQUIRED_FILES = (
    "__init__.py",
    "main.py",
    "metadata.yaml",
    "_conf_schema.json",
    "requirements.txt",
    "README.md",
    "LICENSE",
)
RUNTIME_DIRECTORIES = ("marvel_rivals_bot", "qq_official", "rendering", "messaging")
OPTIONAL_RELEASE_FILES = ("extras/astrbot-t2i/marvel_rivals.html",)
RUNTIME_ASSETS = frozenset({
    "rendering/assets/part-news-bg_ac16ec22.png",
    "rendering/assets/list-l_8a1441f6.png",
    "rendering/assets/logo_95906827.png",
})
FORBIDDEN_PARTS = {
    ".git",
    ".github",
    "tests",
    "tools",
    "captures",
    "debug-responses",
    "__pycache__",
}
RUNTIME_SUFFIXES = {".py"}
VERSION_RE = re.compile(r"^\s*version:\s*['\"]?([^'\"\s#]+)", re.MULTILINE)
MAIN_VERSION_RE = re.compile(
    r"@register\(\s*['\"][^'\"]+['\"]\s*,\s*['\"][^'\"]+['\"]\s*,"
    r"\s*['\"][^'\"]*['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
PROJECT_VERSION_RE = re.compile(r"^\s*version\s*=\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
GITHUB_REPO_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+(?:\.git)?$")


def _match(pattern: re.Pattern[str], text: str, label: str) -> str:
    match = pattern.search(text)
    if not match:
        raise ValueError(f"无法从 {label} 读取版本")
    return match.group(1)


def read_versions(root: Path = ROOT) -> tuple[str, str, str]:
    metadata = (root / "metadata.yaml").read_text(encoding="utf-8")
    main = (root / "main.py").read_text(encoding="utf-8")
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    return (
        _match(VERSION_RE, metadata, "metadata.yaml"),
        _match(MAIN_VERSION_RE, main, "main.py register"),
        _match(PROJECT_VERSION_RE, project, "pyproject.toml"),
    )


def metadata_value(key: str, root: Path = ROOT) -> str:
    text = (root / "metadata.yaml").read_text(encoding="utf-8")
    match = re.search(rf"^\s*{re.escape(key)}:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"metadata.yaml 缺少 {key}")
    return match.group(1).strip()


def validate_source(root: Path = ROOT, tag: str | None = None) -> str:
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            raise ValueError(f"缺少插件文件: {relative}")
    for directory in RUNTIME_DIRECTORIES:
        if not (root / directory).is_dir():
            raise ValueError(f"缺少运行目录: {directory}")

    metadata_version, main_version, project_version = read_versions(root)
    if not SEMVER_RE.fullmatch(metadata_version):
        raise ValueError(f"metadata.yaml 版本不是 SemVer: {metadata_version}")
    if len({metadata_version, main_version, project_version}) != 1:
        raise ValueError(
            "版本不一致: "
            f"metadata.yaml={metadata_version}, main.py={main_version}, pyproject.toml={project_version}"
        )
    if metadata_value("name", root) != PLUGIN_NAME:
        raise ValueError(f"插件 name 必须是 {PLUGIN_NAME}")
    author = metadata_value("author", root)
    if not author or "/" in author:
        raise ValueError("插件 author 必须是非空且不含 '/' 的字符串")
    repo = metadata_value("repo", root)
    if not GITHUB_REPO_RE.fullmatch(repo):
        raise ValueError("metadata.yaml repo 必须是 HTTPS GitHub 仓库地址")
    if tag is not None:
        if not tag.startswith("v") or tag[1:] != metadata_version:
            raise ValueError(f"Git tag {tag} 与插件版本 {metadata_version} 不一致")
    return metadata_version


def _release_files(root: Path) -> list[Path]:
    files = [root / relative for relative in REQUIRED_FILES]
    for directory in RUNTIME_DIRECTORIES:
        for path in (root / directory).rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in FORBIDDEN_PARTS for part in relative.parts):
                continue
            if any(part.startswith(".") for part in relative.parts):
                raise ValueError(f"运行目录包含禁止路径: {relative}")
            if path.suffix not in RUNTIME_SUFFIXES and relative.as_posix() not in RUNTIME_ASSETS:
                raise ValueError(f"运行目录包含未允许的文件类型: {relative}")
            files.append(path)
    for relative in OPTIONAL_RELEASE_FILES:
        path = root / relative
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def build_archive(output: Path, root: Path = ROOT, tag: str | None = None) -> Path:
    version = validate_source(root, tag)
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _release_files(root)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    if output.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError(f"发布包超过 16 MB 限制: {output.stat().st_size} bytes")
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    if not set(REQUIRED_FILES).issubset(names):
        raise ValueError("发布包缺少 AstrBot 必需文件")
    if any(any(part in FORBIDDEN_PARTS for part in Path(name).parts) for name in names):
        raise ValueError("发布包包含被禁止的开发文件")
    if any(name.endswith((".pyc", ".pyo")) or name.startswith(".") for name in names):
        raise ValueError("发布包包含缓存或隐藏文件")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate source and version consistency")
    parser.add_argument("--build", type=Path, metavar="ZIP", help="build a release zip")
    parser.add_argument("--tag", help="validate a tag such as v0.12.4")
    args = parser.parse_args(argv)
    if not args.check and not args.build:
        parser.error("至少指定 --check 或 --build")
    try:
        version = validate_source(ROOT, args.tag)
        if args.build:
            build_archive(args.build, ROOT, args.tag)
            print(f"built {args.build} ({version})")
        else:
            print(f"validated {version}")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
