#!/usr/bin/env python3
"""Replace decrypt files from workspace_d while keeping decrypt filenames.

The script matches files by relative path after normalizing numeric IDs.
It is useful for replacing files like:

  decrypt/Battle_Textures_LeaderSkinVs_vs_1004_left
  workspace_d/Battle_Textures_LeaderSkinVs_vs_1216_left

Both normalize to:

  Battle_Textures_LeaderSkinVs_vs_{ID}_left

Only file contents are copied. The files in decrypt keep their original names.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DECRYPT = SCRIPT_DIR / "decrypt"
DEFAULT_WORKSPACE_D = SCRIPT_DIR / "workspace_d"


def normalize_relative_path(path: Path, min_digits: int) -> str:
    return re.sub(rf"\d{{{min_digits},}}", "{ID}", path.as_posix())


def natural_key(path: Path) -> list[object]:
    parts: list[object] = []
    for chunk in re.split(r"(\d+)", path.as_posix()):
        parts.append(int(chunk) if chunk.isdigit() else chunk)
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
    decrypt_dir: Path,
    workspace_d_dir: Path,
    min_digits: int,
) -> list[tuple[Path, Path, str]]:
    target_groups = collect_files(decrypt_dir, min_digits)
    source_groups = collect_files(workspace_d_dir, min_digits)

    errors: list[str] = []
    plan: list[tuple[Path, Path, str]] = []

    for key in sorted(target_groups):
        targets = target_groups[key]
        sources = source_groups.get(key)

        if not sources:
            errors.append(f"missing workspace_d match for: {key}")
            continue

        if len(sources) != len(targets):
            errors.append(
                f"count mismatch for {key}: "
                f"decrypt={len(targets)}, workspace_d={len(sources)}"
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


def print_plan(plan: list[tuple[Path, Path, str]], decrypt_dir: Path, workspace_d_dir: Path) -> None:
    for source, target, key in plan:
        print(key)
        print(f"  source: {source.relative_to(workspace_d_dir)}")
        print(f"  target: {target.relative_to(decrypt_dir)}")
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
        description="Replace decrypt files from workspace_d while keeping decrypt filenames."
    )
    parser.add_argument("--decrypt", type=Path, default=DEFAULT_DECRYPT, help="decrypt folder")
    parser.add_argument(
        "--workspace-d",
        type=Path,
        default=DEFAULT_WORKSPACE_D,
        help="workspace_d folder",
    )
    parser.add_argument(
        "--min-digits",
        type=int,
        default=4,
        help="numeric runs with at least this many digits are treated as replaceable IDs",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually overwrite decrypt files. Without this, only prints the plan.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="after applying, verify target file hashes equal source file hashes",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    decrypt_dir = args.decrypt.resolve()
    workspace_d_dir = args.workspace_d.resolve()

    if not decrypt_dir.is_dir():
        raise FileNotFoundError(f"decrypt folder not found: {decrypt_dir}")
    if not workspace_d_dir.is_dir():
        raise FileNotFoundError(f"workspace_d folder not found: {workspace_d_dir}")

    plan = build_plan(
        decrypt_dir=decrypt_dir,
        workspace_d_dir=workspace_d_dir,
        min_digits=args.min_digits,
    )

    print_plan(plan, decrypt_dir, workspace_d_dir)
    print(f"planned: {len(plan)} files")

    if args.apply:
        apply_plan(plan)
        print(f"replaced: {len(plan)} files")
        if args.verify:
            all_ok = verify_plan(plan)
            print(f"all_match={all_ok}")
            return 0 if all_ok else 1
    else:
        print("Run again with --apply to overwrite decrypt files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
