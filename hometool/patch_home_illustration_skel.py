# -*- coding: utf-8 -*-
"""Patch Shadowverse HomeIllustration UnityFS bundles from one id to another.

The script looks for files named:

  Prefabs_UI_HomeIllustration_hi_<old_id>

in the same directory as this script.  It infers <old_id> from the file name,
asks for the destination id if it was not provided on the command line, then
writes a new bundle named:

  Prefabs_UI_HomeIllustration_hi_<new_id>

It patches normal Unity object names/path names and TextAsset payloads.  Spine
.skel TextAsset payloads are handled through Spine's length-prefixed string
format, so ids with different lengths are safe.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


FILE_RE = re.compile(r"^Prefabs_UI_HomeIllustration_hi_(\d+)$")
DEFAULT_UNITY_VERSION = "2022.3.54f1"


@dataclass
class SpineStringHit:
    offset: int
    old_text: str
    new_text: str


@dataclass
class TextScriptEdit:
    name: str
    mode: str
    count: int


@dataclass
class PatchReport:
    source: Path
    output: Path
    old_id: str
    new_id: str
    changed_objects: int = 0
    name_edits: list[str] = field(default_factory=list)
    script_edits: list[TextScriptEdit] = field(default_factory=list)
    spine_edits: list[tuple[str, list[SpineStringHit]]] = field(default_factory=list)
    typetree_edits: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    old_cab: str | None = None
    new_cab: str | None = None
    old_res: str | None = None
    new_res: str | None = None
    cab_raw_hits: int = 0


def read_varuint(data: bytes, pos: int) -> tuple[int, int] | None:
    value = 0
    shift = 0
    for i in range(5):
        at = pos + i
        if at >= len(data):
            return None
        b = data[at]
        value |= (b & 0x7F) << shift
        if b & 0x80 == 0:
            return value, at + 1
        shift += 7
    return None


def write_varuint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def is_reasonable_spine_text(raw: bytes) -> bool:
    if not raw or len(raw) > 4096:
        return False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in "\t\r\n":
            return False
    return True


def patch_spine_binary_strings(blob: bytes, old_id: str, new_id: str) -> tuple[bytes, list[SpineStringHit]]:
    """Patch length-prefixed UTF-8 strings in Spine binary .skel data."""
    old_raw = old_id.encode("utf-8")
    out = bytearray()
    hits: list[SpineStringHit] = []
    i = 0

    while i < len(blob):
        decoded = read_varuint(blob, i)
        if decoded is None:
            out.append(blob[i])
            i += 1
            continue

        value, text_start = decoded
        text_len = value - 1
        text_end = text_start + text_len
        if value == 0 or text_len < 0 or text_end > len(blob):
            out.append(blob[i])
            i += 1
            continue

        raw_text = blob[text_start:text_end]
        if old_raw in raw_text and is_reasonable_spine_text(raw_text):
            old_text = raw_text.decode("utf-8")
            new_text = old_text.replace(old_id, new_id)
            new_bytes = new_text.encode("utf-8")
            out.extend(write_varuint(len(new_bytes) + 1))
            out.extend(new_bytes)
            hits.append(SpineStringHit(i, old_text, new_text))
            i = text_end
        else:
            out.append(blob[i])
            i += 1

    return bytes(out), hits


def text_to_bytes(value: str | bytes | bytearray) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    return value.encode("utf-8", "surrogateescape")


def bytes_to_text(value: bytes) -> str:
    return value.decode("utf-8", "surrogateescape")


def is_plain_text(raw: bytes) -> bool:
    if not raw:
        return False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if "\x00" in text:
        return False
    bad = 0
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in "\t\r\n":
            bad += 1
    return bad == 0


def load_unitypy():
    try:
        import UnityPy
        from UnityPy import config as unitypy_config
    except ImportError as exc:
        raise RuntimeError("UnityPy is required. Install with: pip install UnityPy lz4") from exc

    unitypy_config.FALLBACK_UNITY_VERSION = DEFAULT_UNITY_VERSION
    return UnityPy


def detect_bundle_cabs(bundle) -> tuple[str | None, str | None]:
    main_key = None
    res_key = None
    for key in bundle.files.keys():
        if key.endswith(".resS"):
            if res_key is None:
                res_key = key
        elif main_key is None:
            main_key = key
    return main_key, res_key


def derive_cab_name(old_main: str, seed: str, occupied: set[str], old_id: str, new_id: str) -> str:
    if not old_main.startswith("CAB-") or len(old_main) < 8:
        return old_main

    forbidden = (old_id, new_id)
    base = old_main[:-2]
    for attempt in range(256):
        suffix = hashlib.blake2s(f"{seed}|{attempt}".encode("utf-8"), digest_size=1).hexdigest()
        candidate = base + suffix
        if candidate == old_main or candidate in occupied:
            continue
        if any(part and part in candidate for part in forbidden):
            continue
        return candidate

    for attempt in range(256):
        digest = hashlib.blake2s(f"{seed}|fallback|{attempt}".encode("utf-8"), digest_size=2).hexdigest()
        candidate = old_main[:-4] + digest if len(old_main) >= 10 else f"CAB-{digest}"
        if candidate == old_main or candidate in occupied:
            continue
        if any(part and part in candidate for part in forbidden):
            continue
        return candidate

    raise RuntimeError(f"unable to derive a unique cab name from {old_main!r}")


def rename_bundle_cabs(bundle, old_main: str | None, new_main: str | None, old_res: str | None, new_res: str | None) -> None:
    if not old_main or not new_main or old_main == new_main:
        return

    new_files = {}
    for key, value in bundle.files.items():
        new_key = key
        if key == old_main:
            new_key = new_main
        elif old_res and new_res and key == old_res:
            new_key = new_res

        if hasattr(value, "name"):
            try:
                value.name = new_key
            except Exception:
                pass
        new_files[new_key] = value
    bundle.files = new_files


def current_raw_data(obj) -> bytes:
    data = getattr(obj, "data", None)
    if data is not None:
        return data
    return obj.get_raw_data()


def patch_cab_raw_refs(env, old_cab: str | None, new_cab: str | None) -> int:
    if not old_cab or not new_cab or old_cab == new_cab:
        return 0
    if len(old_cab.encode("ascii")) != len(new_cab.encode("ascii")):
        return 0

    old_ascii = old_cab.encode("ascii")
    new_ascii = new_cab.encode("ascii")
    old_utf16 = old_cab.encode("utf-16le")
    new_utf16 = new_cab.encode("utf-16le")
    hits = 0

    for obj in env.objects:
        try:
            raw = current_raw_data(obj)
        except Exception:
            continue
        count = raw.count(old_ascii) + raw.count(old_utf16)
        if count == 0:
            continue
        patched = raw.replace(old_ascii, new_ascii).replace(old_utf16, new_utf16)
        obj.set_raw_data(patched)
        hits += count
    return hits


def replace_typetree_strings(value, old_id: str, new_id: str, path: str = "") -> tuple[object, list[str]]:
    edits: list[str] = []

    if isinstance(value, str):
        if old_id not in value:
            return value, edits
        new_value = value.replace(old_id, new_id)
        edits.append(f"{path or '<root>'}: {value!r} -> {new_value!r}")
        return new_value, edits

    if isinstance(value, list):
        changed = False
        new_items = []
        for index, item in enumerate(value):
            new_item, item_edits = replace_typetree_strings(item, old_id, new_id, f"{path}[{index}]" if path else f"[{index}]")
            if item_edits:
                changed = True
                edits.extend(item_edits)
            new_items.append(new_item)
        return (new_items if changed else value), edits

    if isinstance(value, tuple):
        changed = False
        new_items = []
        for index, item in enumerate(value):
            new_item, item_edits = replace_typetree_strings(item, old_id, new_id, f"{path}[{index}]" if path else f"[{index}]")
            if item_edits:
                changed = True
                edits.extend(item_edits)
            new_items.append(new_item)
        return (tuple(new_items) if changed else value), edits

    if isinstance(value, dict):
        changed = False
        new_dict = {}
        for key, item in value.items():
            new_key = key
            key_path = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and old_id in key:
                new_key = key.replace(old_id, new_id)
                changed = True
                edits.append(f"{path or '<root>'} key: {key!r} -> {new_key!r}")

            new_item, item_edits = replace_typetree_strings(item, old_id, new_id, key_path)

            if item_edits:
                changed = True
                edits.extend(item_edits)
            new_dict[new_key] = new_item
        return (new_dict if changed else value), edits

    return value, edits


def patch_mono_typetree_strings(obj, old_id: str, new_id: str, dry_run: bool, label: str) -> list[str]:
    if obj.type.name != "MonoBehaviour":
        return []

    tree = obj.read_typetree()
    patched_tree, edits = replace_typetree_strings(tree, old_id, new_id)
    if not edits:
        return []
    if not dry_run:
        obj.save_typetree(patched_tree)
    return [f"{label}: {item}" for item in edits]


def discover_targets(tool_dir: Path) -> list[Path]:
    targets: list[Path] = []
    for path in sorted(tool_dir.iterdir()):
        if not path.is_file():
            continue
        if FILE_RE.match(path.name):
            targets.append(path)
    return targets


def infer_old_id(path: Path) -> str:
    match = FILE_RE.match(path.name)
    if not match:
        raise ValueError(f"not a HomeIllustration bundle name: {path.name}")
    return match.group(1)


def choose_target(tool_dir: Path, requested: Path | None, source_id: str | None, new_id: str | None) -> Path:
    if requested is not None:
        return requested.resolve()

    targets = discover_targets(tool_dir)
    if source_id:
        targets = [p for p in targets if infer_old_id(p) == source_id]
    elif new_id:
        non_target_id_files = [p for p in targets if infer_old_id(p) != new_id]
        if non_target_id_files:
            targets = non_target_id_files

    if not targets:
        raise RuntimeError(f"no Prefabs_UI_HomeIllustration_hi_<id> file found in {tool_dir}")

    if len(targets) == 1:
        return targets[0]

    print("Found multiple HomeIllustration files:")
    for idx, path in enumerate(targets, 1):
        print(f"  {idx}. {path.name}")
    raw = input(f"Select source file [1-{len(targets)}] (Enter = 1): ").strip()
    if not raw:
        return targets[0]
    try:
        index = int(raw)
    except ValueError as exc:
        raise RuntimeError("selection must be a number") from exc
    if index < 1 or index > len(targets):
        raise RuntimeError("selection out of range")
    return targets[index - 1]


def patch_bundle(
    UnityPy,
    source: Path,
    output: Path,
    old_id: str,
    new_id: str,
    packer: str,
    dry_run: bool,
    occupied_cabs: set[str],
    rename_cab: bool,
) -> PatchReport:
    env = UnityPy.load(str(source))
    bundle = env.file
    report = PatchReport(source=source, output=output, old_id=old_id, new_id=new_id)

    old_cab, old_res = detect_bundle_cabs(bundle)
    report.old_cab = old_cab
    report.old_res = old_res
    if old_cab and rename_cab:
        seed = f"{source.name}|{output.name}|{old_id}|{new_id}"
        report.new_cab = derive_cab_name(old_cab, seed, occupied_cabs, old_id, new_id)
        report.new_res = f"{report.new_cab}.resS" if old_res else None
        occupied_cabs.add(report.new_cab)

    old_raw = old_id.encode("utf-8")

    for obj in env.objects:
        try:
            data = obj.read()
        except Exception as exc:
            report.warnings.append(f"path_id={getattr(obj, 'path_id', '?')}: read failed: {exc}")
            continue

        object_changed = False
        label = f"{obj.type.name}"
        name = getattr(data, "m_Name", getattr(data, "name", ""))
        if name:
            label = f"{label} {name!r}"

        for attr in ("m_Name", "m_PathName", "m_AssetBundleName"):
            value = getattr(data, attr, None)
            if isinstance(value, str) and old_id in value:
                new_value = value.replace(old_id, new_id)
                setattr(data, attr, new_value)
                object_changed = True
                report.name_edits.append(f"{attr}: {value!r} -> {new_value!r} ({label})")

        container = getattr(data, "m_Container", None)
        if isinstance(container, list):
            new_container = []
            container_changed = False
            for item in container:
                if isinstance(item, tuple) and item and isinstance(item[0], str) and old_id in item[0]:
                    new_key = item[0].replace(old_id, new_id)
                    new_container.append((new_key, *item[1:]))
                    container_changed = True
                    report.name_edits.append(f"m_Container: {item[0]!r} -> {new_key!r} ({label})")
                else:
                    new_container.append(item)
            if container_changed:
                data.m_Container = new_container
                object_changed = True

        if hasattr(data, "m_Script") and isinstance(data.m_Script, (str, bytes, bytearray)):
            script_bytes = text_to_bytes(data.m_Script)
            if old_raw in script_bytes:
                is_skel_payload = isinstance(name, str) and name.endswith(".skel")
                if is_skel_payload:
                    patched_bytes, spine_hits = patch_spine_binary_strings(script_bytes, old_id, new_id)
                    if not spine_hits:
                        report.warnings.append(
                            f"{label}: found id {old_id!r} in .skel m_Script, but no safe Spine string was detected"
                        )
                        spine_hits = []
                else:
                    patched_bytes, spine_hits = script_bytes, []

                if is_skel_payload and spine_hits:
                    data.m_Script = bytes_to_text(patched_bytes)
                    object_changed = True
                    report.spine_edits.append((label, spine_hits))
                elif is_plain_text(script_bytes):
                    old_text = bytes_to_text(script_bytes)
                    new_text = old_text.replace(old_id, new_id)
                    data.m_Script = new_text
                    object_changed = True
                    report.script_edits.append(TextScriptEdit(label, "plain-text", old_text.count(old_id)))
                elif not is_skel_payload:
                    report.warnings.append(f"{label}: found id {old_id!r} in m_Script, but no safe text format was detected")

        if object_changed:
            report.changed_objects += 1
            if not dry_run:
                data.save()

        try:
            typetree_edits = patch_mono_typetree_strings(obj, old_id, new_id, dry_run, label)
        except Exception as exc:
            report.warnings.append(f"{label}: typetree string scan failed: {exc}")
            typetree_edits = []
        if typetree_edits:
            report.typetree_edits.extend(typetree_edits)
            if not object_changed:
                report.changed_objects += 1

    if report.changed_objects == 0:
        raise RuntimeError("no safe edits were found")

    if not dry_run:
        if rename_cab:
            rename_bundle_cabs(bundle, report.old_cab, report.new_cab, report.old_res, report.new_res)
            report.cab_raw_hits = patch_cab_raw_refs(env, report.old_cab, report.new_cab)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(env.file.save(packer=packer))

    return report


def verify_bundle(UnityPy, output: Path, old_id: str, new_id: str, report: PatchReport) -> None:
    env = UnityPy.load(str(output))
    leftovers: list[str] = []
    old_raw = old_id.encode("utf-8")
    new_raw = new_id.encode("utf-8")
    saw_new_id = False

    keys = set(env.file.files.keys())
    if report.new_cab and report.new_cab not in keys:
        raise RuntimeError(f"renamed CAB key was not found: {report.new_cab}")
    if report.old_cab and report.old_cab in keys:
        raise RuntimeError(f"old CAB key still exists: {report.old_cab}")
    if report.old_res and report.old_res in keys:
        raise RuntimeError(f"old resS key still exists: {report.old_res}")
    if report.new_res and report.new_res not in keys:
        raise RuntimeError(f"renamed resS key was not found: {report.new_res}")

    for obj in env.objects:
        try:
            raw = obj.get_raw_data()
        except Exception:
            continue
        if new_raw in raw:
            saw_new_id = True
        if old_raw in raw:
            try:
                data = obj.read()
                name = getattr(data, "m_Name", getattr(data, "name", ""))
            except Exception:
                name = ""
            leftovers.append(f"{obj.type.name} {name}".strip())

    if leftovers:
        preview = ", ".join(leftovers[:12])
        if len(leftovers) > 12:
            preview += f", ... (+{len(leftovers) - 12})"
        raise RuntimeError(f"old id still exists in: {preview}")
    if not saw_new_id:
        raise RuntimeError(f"new id {new_id!r} was not found after saving")


def print_report(report: PatchReport, dry_run: bool) -> None:
    print(f"Source: {report.source}")
    print(f"Output: {report.output}")
    print(f"Old id: {report.old_id}")
    print(f"New id: {report.new_id}")
    print(f"Changed objects: {report.changed_objects}")
    if report.old_cab and report.new_cab:
        res_note = f" / {report.new_res}" if report.new_res else ""
        print(f"CAB: {report.old_cab} -> {report.new_cab}{res_note}")

    if report.name_edits:
        print()
        print("[Name/path edits]")
        for item in report.name_edits:
            print(f"  - {item}")

    if report.script_edits:
        print()
        print("[Plain TextAsset edits]")
        for item in report.script_edits:
            print(f"  - {item.name}: {item.count} replacement(s)")

    if report.spine_edits:
        print()
        print("[Spine .skel edits]")
        for label, hits in report.spine_edits:
            print(f"  - {label}: {len(hits)} string(s)")
            for hit in hits:
                print(f"      @{hit.offset}: {hit.old_text!r} -> {hit.new_text!r}")

    if report.typetree_edits:
        print()
        print("[MonoBehaviour typetree edits]")
        for item in report.typetree_edits:
            print(f"  - {item}")

    if report.cab_raw_hits:
        print()
        print(f"[CAB raw refs] {report.cab_raw_hits} replacement(s)")

    if report.warnings:
        print()
        print("[Warnings]")
        for item in report.warnings:
            print(f"  - {item}")

    if dry_run:
        print()
        print("[DRY-RUN] No file was written.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch HomeIllustration bundle ids.")
    parser.add_argument("new_id", nargs="?", help="destination numeric id, e.g. 1004")
    parser.add_argument("--target", type=Path, help="source bundle file; default: auto-discover in script directory")
    parser.add_argument("--source-id", help="old id; default: inferred from file name")
    parser.add_argument("--output", type=Path, help="output file; default: same directory with the new id in its name")
    parser.add_argument("--packer", default="original", choices=["original", "lz4", "none"], help="Unity bundle packing mode")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing output")
    parser.add_argument("--dry-run", action="store_true", help="only report planned edits")
    parser.add_argument("--no-verify", action="store_true", help="skip reload verification after writing")
    parser.add_argument("--no-cab-rename", action="store_true", help="do not rename the bundle CAB/resS keys")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tool_dir = Path(__file__).resolve().parent

    if not args.new_id:
        args.new_id = input("Target id / New id: ").strip()
    if not args.new_id or not args.new_id.isdigit():
        print("[ERROR] Target id must be numeric.", file=sys.stderr)
        return 2

    source = choose_target(tool_dir, args.target, args.source_id, args.new_id)
    if not source.is_file():
        print(f"[ERROR] Source file not found: {source}", file=sys.stderr)
        return 2

    old_id = args.source_id or infer_old_id(source)
    if old_id == args.new_id:
        print("[ERROR] Old id and new id are the same.", file=sys.stderr)
        return 2

    output = args.output or source.with_name(FILE_RE.sub(f"Prefabs_UI_HomeIllustration_hi_{args.new_id}", source.name))
    if output.exists() and not args.overwrite and not args.dry_run:
        print(f"[ERROR] Output already exists: {output}", file=sys.stderr)
        print("        Use --overwrite if you want to replace it.", file=sys.stderr)
        return 2

    try:
        UnityPy = load_unitypy()
        occupied_cabs: set[str] = set()
        for target in discover_targets(tool_dir):
            try:
                env = UnityPy.load(str(target))
                old_cab, _ = detect_bundle_cabs(env.file)
                if old_cab:
                    occupied_cabs.add(old_cab)
            except Exception:
                pass

        report = patch_bundle(
            UnityPy=UnityPy,
            source=source,
            output=output,
            old_id=old_id,
            new_id=args.new_id,
            packer=args.packer,
            dry_run=args.dry_run,
            occupied_cabs=occupied_cabs,
            rename_cab=not args.no_cab_rename,
        )
        print_report(report, args.dry_run)

        if not args.dry_run and not args.no_verify:
            verify_bundle(UnityPy, output, old_id, args.new_id, report)
            print()
            print("Reload check: OK")
            print(f"Written: {output}")
            print(f"New size: {output.stat().st_size} bytes")
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
