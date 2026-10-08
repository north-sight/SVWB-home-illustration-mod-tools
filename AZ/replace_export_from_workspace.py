#!/usr/bin/env python3
"""Replace export files with corresponding workspace files while keeping names.

This is meant for BYD_ModStudio export folders. It matches files by relative
path shape after normalizing numeric IDs, then copies workspace file contents
onto export files without changing export folder names or filenames.

Example:
  export/Battle_Textures_LeaderSkinVs_vs_1004_left/vs_1004_left.png
  workspace/Battle_Textures_LeaderSkinVs_vs_1216_left/vs_1216_left.png

Both normalize to:
  Battle_Textures_LeaderSkinVs_vs_{ID}_left/vs_{ID}_left.png
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EXPORT = SCRIPT_DIR / "export"
DEFAULT_WORKSPACE = SCRIPT_DIR / "workspace"


def normalize_relative_path(path: Path, min_digits: int) -> str:
    text = path.as_posix()
    return re.sub(rf"\d{{{min_digits},}}", "{ID}", text)


def natural_key(path: Path) -> list[object]:
    parts: list[object] = []
    for chunk in re.split(r"(\d+)", path.as_posix()):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            parts.append(chunk)
    return parts


def collect_files(base: Path, min_digits: int) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    for file_path in base.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(base)
        key = normalize_relative_path(rel_path, min_digits)
        groups[key].append(file_path)

    return {
        key: sorted(paths, key=lambda p: natural_key(p.relative_to(base)))
        for key, paths in groups.items()
    }


def build_plan(
    export_dir: Path,
    workspace_dir: Path,
    min_digits: int,
    allow_extra_sources: bool,
) -> list[tuple[Path, Path, str]]:
    export_groups = collect_files(export_dir, min_digits)
    workspace_groups = collect_files(workspace_dir, min_digits)

    plan: list[tuple[Path, Path, str]] = []
    errors: list[str] = []

    for key in sorted(export_groups):
        targets = export_groups[key]
        sources = workspace_groups.get(key)

        if not sources:
            errors.append(f"missing workspace match for: {key}")
            continue

        if len(sources) != len(targets):
            if allow_extra_sources and len(sources) > len(targets):
                sources = sources[: len(targets)]
            else:
                errors.append(
                    f"count mismatch for {key}: "
                    f"export={len(targets)}, workspace={len(sources)}"
                )
                continue

        for source, target in zip(sources, targets):
            plan.append((source, target, key))

    if errors:
        raise RuntimeError("\n".join(errors))

    return plan


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_plan(plan: list[tuple[Path, Path, str]], export_dir: Path, workspace_dir: Path) -> None:
    for source, target, key in plan:
        print(key)
        print(f"  source: {source.relative_to(workspace_dir)}")
        print(f"  target: {target.relative_to(export_dir)}")
        print(f"  keep:   {target.name}")


def apply_plan(plan: list[tuple[Path, Path, str]]) -> None:
    for source, target, _key in plan:
        shutil.copy2(source, target)


def verify_plan(plan: list[tuple[Path, Path, str]]) -> bool:
    ok = True
    for source, target, key in plan:
        same = sha256(source) == sha256(target)
        ok = ok and same
        print(f"verify={same} {key}")
    return ok


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace BYD_ModStudio export files from workspace while keeping export names."
    )
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT, help="export folder")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE, help="workspace folder")
    parser.add_argument(
        "--min-digits",
        type=int,
        default=4,
        help="numeric runs with at least this many digits are treated as replaceable IDs",
    )
    parser.add_argument(
        "--allow-extra-sources",
        action="store_true",
        help="allow a matching workspace group to contain more files than export",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually overwrite export files. Without this, only prints the plan.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="after applying, verify target file hashes equal source file hashes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export_dir = args.export.resolve()
    workspace_dir = args.workspace.resolve()

    if not export_dir.is_dir():
        raise FileNotFoundError(f"export folder not found: {export_dir}")
    if not workspace_dir.is_dir():
        raise FileNotFoundError(f"workspace folder not found: {workspace_dir}")

    plan = build_plan(
        export_dir=export_dir,
        workspace_dir=workspace_dir,
        min_digits=args.min_digits,
        allow_extra_sources=args.allow_extra_sources,
    )

    print_plan(plan, export_dir, workspace_dir)
    print(f"planned: {len(plan)} files")

    if args.apply:
        apply_plan(plan)
        print(f"replaced: {len(plan)} files")
        if args.verify:
            all_ok = verify_plan(plan)
            print(f"all_match={all_ok}")
            return 0 if all_ok else 1
    else:
        print("Run again with --apply to overwrite export files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
