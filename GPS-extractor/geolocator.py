#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import exifread


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _first(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v:
            return v
    return None


def _exifread_get_str(tags: Dict[str, Any], key: str) -> Optional[str]:
    tag = tags.get(key)
    if not tag:
        return None
    vals = getattr(tag, "values", None)
    if isinstance(vals, (list, tuple)) and vals:
        return _clean(vals[0])
    return _clean(tag)


def _ratio_to_float(x: Any) -> float:
    num = getattr(x, "num", None)
    den = getattr(x, "den", None)
    if num is not None and den not in (None, 0):
        return float(num) / float(den)
    return float(x)


def _dms_to_decimal(dms_tag: Any, ref_tag: Any) -> float:
    dms = list(getattr(dms_tag, "values", dms_tag))
    if len(dms) != 3:
        raise ValueError(f"Expected 3 DMS components, got {len(dms)}")

    deg, minutes, sec = dms
    decimal = _ratio_to_float(deg) + _ratio_to_float(minutes) / 60.0 + _ratio_to_float(sec) / 3600.0

    ref = str(getattr(ref_tag, "values", [ref_tag])[0]).strip().upper()
    if ref in {"S", "W"}:
        decimal = -decimal
    elif ref in {"N", "E"}:
        pass
    else:
        raise ValueError(f"Unexpected GPS reference: {ref!r}")

    return decimal


def _map_url(lat: float, lon: float) -> str:
    return f"http://maps.google.com/?q={lat:.6f},{lon:.6f}"


def extract_record(file_path: str, include_tags: bool) -> Dict[str, Any]:
    errors: List[str] = []
    out: Dict[str, Any] = {
        "file": file_path,
        "exif_present": False,
        "captured_with": None,
        "date_taken": None,
        "gps": None,
        "errors": errors,
        "tool": "exifread",
    }

    try:
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, details=False)

        out["exif_present"] = bool(tags)

        if include_tags:
            out["tags"] = {k: str(v) for k, v in tags.items()}

        make = _exifread_get_str(tags, "Image Make")
        model = _exifread_get_str(tags, "Image Model")
        software = _exifread_get_str(tags, "Image Software")

        if make or model:
            out["captured_with"] = " ".join([x for x in (make, model) if x])
        else:
            out["captured_with"] = software

        out["date_taken"] = _first(
            _exifread_get_str(tags, "EXIF DateTimeOriginal"),
            _exifread_get_str(tags, "EXIF DateTimeDigitized"),
            _exifread_get_str(tags, "Image DateTime"),
        )

        lat_tag = tags.get("GPS GPSLatitude")
        lat_ref_tag = tags.get("GPS GPSLatitudeRef")
        lon_tag = tags.get("GPS GPSLongitude")
        lon_ref_tag = tags.get("GPS GPSLongitudeRef")

        if lat_tag and lat_ref_tag and lon_tag and lon_ref_tag:
            lat = _dms_to_decimal(lat_tag, lat_ref_tag)
            lon = _dms_to_decimal(lon_tag, lon_ref_tag)
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                out["gps"] = {"lat": lat, "lon": lon, "map_url": _map_url(lat, lon)}

    except Exception as e:
        errors.append(str(e))

    return out


def iter_files(input_path: str, extensions: Iterable[str], recursive: bool) -> List[str]:
    p = Path(input_path)
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}

    if p.is_file():
        return [str(p)]

    results: List[str] = []
    if recursive:
        for root, _, files in os.walk(p):
            for fn in files:
                if Path(fn).suffix.lower() in exts:
                    results.append(str(Path(root) / fn))
    else:
        for fn in os.listdir(p):
            fp = p / fn
            if fp.is_file() and fp.suffix.lower() in exts:
                results.append(str(fp))

    results.sort()
    return results


def write_jsonl(records: List[Dict[str, Any]], out_path: Optional[str]) -> None:
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            for obj in records:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    else:
        for obj in records:
            print(json.dumps(obj, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description="EXIF extractor (exifread-only) with JSONL output")
    ap.add_argument("input", help="Image file or directory")
    ap.add_argument("--jsonl", action="store_true", help="Emit JSONL (one object per line)")
    ap.add_argument("--jsonl-out", metavar="PATH", help="Write JSONL to PATH (implies --jsonl)")
    ap.add_argument("--include-tags", action="store_true", help="Include raw EXIF tags under 'tags'")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON (non-JSONL mode)")
    ap.add_argument(
        "--extensions",
        default=".jpg,.jpeg,.png,.tif,.tiff,.heic",
        help="Comma-separated extensions to include",
    )
    ap.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    args = ap.parse_args()

    input_path = args.input
    p = Path(input_path)
    exts = [e.strip() for e in args.extensions.split(",") if e.strip()]

    jsonl_mode = bool(args.jsonl or args.jsonl_out)

    if not p.exists():
        obj = {
            "file": input_path,
            "exif_present": False,
            "captured_with": None,
            "date_taken": None,
            "gps": None,
            "errors": ["File or directory not found."],
            "tool": "exifread",
        }
        if jsonl_mode:
            write_jsonl([obj], args.jsonl_out)
        else:
            print(json.dumps([obj], indent=2 if args.pretty else None, ensure_ascii=False))
        return 2

    files = iter_files(input_path, exts, recursive=(not args.no_recursive))
    records = [extract_record(fp, include_tags=args.include_tags) for fp in files]

    if jsonl_mode:
        write_jsonl(records, args.jsonl_out)
    else:
        print(json.dumps(records, indent=2 if args.pretty else None, ensure_ascii=False))

    # preserve single-file exit codes
    if p.is_file():
        rec = records[0]
        if rec["errors"]:
            return 3
        if rec["gps"] and rec["gps"].get("lat") is not None and rec["gps"].get("lon") is not None:
            return 0
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
