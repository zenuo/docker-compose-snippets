#!/usr/bin/env python3
"""Replace docker-compose image names using a JSON original->mirror map."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

COMPOSE_NAMES = {
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG = REPO_ROOT / "image-mirrors.json"

IMAGE_LINE_RE = re.compile(
    r"^(?P<indent>\s*)image:\s*"
    r"(?:(?P<quote>['\"])(?P<quoted>[^'\"]+)(?P=quote)|(?P<unquoted>[^\s#'\"]+))"
    r"(?P<trailing>\s*(?:#.*)?)?$"
)
IMAGE_COMMENT_RE = re.compile(r"^(?P<indent>\s*)#\s*(?P<ref>\S+)\s*$")
IMAGE_REF_RE = re.compile(
    r"^(?:"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]+)?/)?"
    r"(?:[A-Za-z0-9._-]+/)*"
    r"[A-Za-z0-9._-]+"
    r"(?::[A-Za-z0-9._-]+)?"
    r"(?:@[A-Za-z0-9:._-]+)?"
    r")$"
)


def split_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def is_image_ref(text: str) -> bool:
    return bool(text) and IMAGE_REF_RE.fullmatch(text) is not None


def load_mapping(config_path: Path) -> dict[str, str]:
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"找不到配置文件: {config_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"配置文件不是合法 JSON: {config_path}: {exc}")

    if not isinstance(raw, dict):
        raise SystemExit(f"配置文件必须是对象（原始链接 -> 镜像链接）: {config_path}")

    mapping: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SystemExit("配置文件的键和值都必须是字符串")
        original = key.strip()
        mirror = value.strip()
        if not original or not mirror:
            raise SystemExit("配置文件中不能有空的原始链接或镜像链接")
        mapping[original] = mirror
    return mapping


def reverse_mapping(mapping: dict[str, str]) -> dict[str, str]:
    reverse: dict[str, str] = {}
    duplicates: list[str] = []
    for original, mirror in mapping.items():
        if mirror in reverse and reverse[mirror] != original:
            duplicates.append(mirror)
            continue
        reverse[mirror] = original
    if duplicates:
        unique = ", ".join(sorted(set(duplicates)))
        print(f"警告: 多个原始链接对应同一镜像，restore 反查将忽略重复项: {unique}", file=sys.stderr)
    return reverse


def find_compose_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            if name in COMPOSE_NAMES:
                found.append(Path(dirpath) / name)
    return sorted(found)


def parse_image_line(content: str) -> dict[str, str] | None:
    match = IMAGE_LINE_RE.fullmatch(content)
    if not match:
        return None
    quote = match.group("quote") or ""
    value = match.group("quoted") if quote else match.group("unquoted")
    trailing = match.group("trailing") or ""
    return {
        "indent": match.group("indent"),
        "quote": quote,
        "value": value,
        "trailing": trailing,
    }


def format_image_line(parsed: dict[str, str], value: str, newline: str) -> str:
    quote = parsed["quote"]
    if quote:
        rendered = f"{quote}{value}{quote}"
    else:
        rendered = value
    return f"{parsed['indent']}image: {rendered}{parsed['trailing']}{newline}"


def parse_image_comment(
    content: str,
    mapping: dict[str, str],
    reverse: dict[str, str],
) -> str | None:
    match = IMAGE_COMMENT_RE.fullmatch(content)
    if not match:
        return None
    ref = match.group("ref")
    if ref in mapping or ref in reverse or is_image_ref(ref):
        return ref
    return None


def process_lines(
    lines: list[str],
    mode: str,
    mapping: dict[str, str],
    reverse: dict[str, str],
) -> list[str]:
    out: list[str] = []
    for line in lines:
        content, newline = split_newline(line)
        parsed = parse_image_line(content)
        if parsed is None:
            out.append(line)
            continue

        prev_content = split_newline(out[-1])[0] if out else ""
        comment_ref = parse_image_comment(prev_content, mapping, reverse) if out else None
        value = parsed["value"]

        if mode == "apply":
            if value in mapping:
                original = value
                new_value = mapping[value]
            elif value in reverse:
                original = reverse[value]
                new_value = value
            else:
                out.append(line)
                continue

            comment_line = f"{parsed['indent']}# {original}{newline}"
            if comment_ref == original:
                pass
            elif comment_ref is not None:
                out[-1] = comment_line
            else:
                out.append(comment_line)
            out.append(format_image_line(parsed, new_value, newline))
            continue

        if mode == "restore":
            original: str | None = None
            if comment_ref is not None:
                original = comment_ref
                out.pop()
            elif value in reverse:
                original = reverse[value]
            elif value in mapping:
                original = value
            else:
                out.append(line)
                continue

            new_line = format_image_line(parsed, original, newline)
            out.append(new_line)
            continue

        out.append(line)
    return out


def process_file(
    path: Path,
    mode: str,
    mapping: dict[str, str],
    reverse: dict[str, str],
) -> bool:
    original_text = path.read_text(encoding="utf-8")
    lines = original_text.splitlines(keepends=True)
    new_lines = process_lines(lines, mode, mapping, reverse)
    new_text = "".join(new_lines)
    if new_text == original_text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 docker-compose 中的镜像在官方名与镜像站之间切换")
    parser.add_argument("mode", choices=("apply", "restore"), help="apply: 换成镜像站; restore: 还原官方名")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"JSON 配置文件（默认: {DEFAULT_CONFIG}）",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="递归查找 compose 的根目录（默认: 当前工作目录）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config.expanduser().resolve()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"根目录不存在: {root}", file=sys.stderr)
        return 1

    mapping = load_mapping(config_path)
    reverse = reverse_mapping(mapping)
    files = find_compose_files(root)
    if not files:
        print(f"未找到 docker-compose 文件: {root}")
        return 0

    changed = [path for path in files if process_file(path, args.mode, mapping, reverse)]
    if not changed:
        print("无变更。")
        return 0

    print("已更改:")
    for path in changed:
        try:
            display = path.relative_to(root)
        except ValueError:
            display = path
        print(f"  {display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
