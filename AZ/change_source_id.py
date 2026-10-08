#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


ID_RE = re.compile(r"(?<!\d)\d{4,}(?!\d)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replace the numeric ID in source.txt.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--new-id", required=True)
    parser.add_argument("--old-id", help="optional explicit old id when multiple ids exist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    new_id = args.new_id.strip()

    if not new_id.isdigit():
        raise SystemExit("[ERROR] new id must contain digits only.")

    text = source.read_text(encoding="utf-8-sig")
    ids = sorted({m.group(0) for m in ID_RE.finditer(text)})
    if not ids:
        raise SystemExit("[ERROR] no 4+ digit id found in source.txt.")

    if args.old_id:
        old_id = args.old_id.strip()
        if old_id not in ids:
            raise SystemExit(f"[ERROR] old id not found in source.txt: {old_id}")
    else:
        old_id = ids[0]

    backup = source.with_suffix(source.suffix + ".bak")
    backup.write_text(text, encoding="utf-8")

    pattern = re.compile(rf"(?<!\d){re.escape(old_id)}(?!\d)")
    new_text = pattern.sub(new_id, text)
    source.write_text(new_text, encoding="utf-8")

    print(f"[OK] Replaced {old_id} -> {new_id}")
    print(f"[OK] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
