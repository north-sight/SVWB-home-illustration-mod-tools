#!/usr/bin/env python3
"""Replace same-length numeric IDs in binary files without repacking.

This is useful when only Unity asset names/paths need to change, for example:

  Battle_Textures_LeaderSkinLow_class_1227 -> Battle_Textures_LeaderSkinLow_class_1317

The script performs byte-level replacement and refuses different-length IDs.
That keeps the output file size exactly the same as the input file.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def default_output_path(input_path: Path, old_id: str, new_id: str) -> Path:
    if old_id in input_path.name:
        return input_path.with_name(input_path.name.replace(old_id, new_id))
    return input_path.with_name(f"{input_path.name}.{old_id}_to_{new_id}")


def replace_bytes(data: bytes, old_id: str, new_id: str) -> tuple[bytes, dict[str, int]]:
    patterns = {
        "ascii": (old_id.encode("ascii"), new_id.encode("ascii")),
        "utf16le": (old_id.encode("utf-16le"), new_id.encode("utf-16le")),
    }

    counts: dict[str, int] = {}
    result = data
    for label, (old_bytes, new_bytes) in patterns.items():
        count = result.count(old_bytes)
        counts[label] = count
        if count:
            result = result.replace(old_bytes, new_bytes)
    return result, counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace a same-length numeric id in a binary file while preserving file size."
    )
    parser.add_argument("input", type=Path, help="input file")
    parser.add_argument("old_id", help="old numeric id, e.g. 1227")
    parser.add_argument("new_id", help="new numeric id, e.g. 1317")
    parser.add_argument("-o", "--output", type=Path, help="output file")
    parser.add_argument("--overwrite", action="store_true", help="allow overwriting output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    old_id = args.old_id.strip()
    new_id = args.new_id.strip()

    if not old_id.isdigit() or not new_id.isdigit():
        raise SystemExit("[ERROR] old_id and new_id must contain digits only.")
    if len(old_id) != len(new_id):
        raise SystemExit("[ERROR] old_id and new_id must have the same digit length.")
    if not input_path.is_file():
        raise SystemExit(f"[ERROR] input file not found: {input_path}")

    output_path = (args.output or default_output_path(input_path, old_id, new_id)).resolve()
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"[ERROR] output already exists: {output_path}")

    data = input_path.read_bytes()
    new_data, counts = replace_bytes(data, old_id, new_id)
    total = sum(counts.values())
    if total == 0:
        raise SystemExit(f"[ERROR] no occurrences of {old_id} found.")
    if len(new_data) != len(data):
        raise SystemExit("[ERROR] output size changed; refusing to write.")

    output_path.write_bytes(new_data)
    print(f"[OK] input:  {input_path}")
    print(f"[OK] output: {output_path}")
    print(f"[OK] replaced ascii={counts['ascii']}, utf16le={counts['utf16le']}")
    print(f"[OK] size: {len(data)} -> {len(new_data)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
