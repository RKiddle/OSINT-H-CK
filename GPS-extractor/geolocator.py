#!/usr/bin/env python3
from __future__ import annotations

"""geolocator.py

Extract EXIF metadata (especially GPS coordinates) from image files.

This script is designed for OSINT / DFIR style workflows where you want to quickly
answer questions like:

- "Does this image contain EXIF data at all?"
- "Which device/software created it?"
- "When was it taken?"
- "Does it contain GPS coordinates and a ready-to-click map URL?"

Typical use cases / examples
----------------------------

1) Single image triage
   Quickly check whether a photo has GPS metadata and get a Google Maps link:

       python3 geolocator.py ~/case/photo.jpg --pretty

   Exit codes (single-file mode):
   - 0: GPS found
   - 1: no GPS found (but file processed)
   - 3: error reading/parsing

2) Bulk extraction for a folder (recursive by default)
   Produce a JSON array you can post-process with jq:

       python3 geolocator.py ./images --pretty | jq '.[] | {file, gps, date_taken}'

3) JSONL output for pipelines
   JSONL is convenient for streaming large sets of files (one JSON object per line):

       python3 geolocator.py ./images --jsonl-out exif.jsonl
       cat exif.jsonl | jq -r 'select(.gps) | .file + "\t" + .gps.map_url'

4) Include raw EXIF tags when you need maximum detail

       python3 geolocator.py ./images --include-tags --pretty

Notes
-----
- GPS coordinates in EXIF are usually stored as Degrees/Minutes/Seconds (DMS) plus
  a reference (N/S/E/W). This script converts DMS to signed decimal degrees.
- Not all image types reliably contain EXIF (e.g., many PNGs). "exif_present" will
  be false if no tags are found.

"""

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import exifread


def _clean(v: Any) -> Optional[str]:
    """Normalize a value to a non-empty string.

    Use case:
        exifread tags may return objects, empty strings, or None. This helper makes
        downstream checks ("if v:") reliable.
    """

    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _first(*vals: Optional[str]) -> Optional[str]:
    """Return the first non-empty string from a list of candidates.

    Use case:
        EXIF date can be stored in different fields depending on camera/software.
        This helper picks the first populated field.
    """

    for v in vals:
        if v:
            return v
    return None


def _exifread_get_str(tags: Dict[str, Any], key: str) -> Optional[str]:
    """Read a tag from exifread's dict and return it as a clean string.

    Example:
        make = _exifread_get_str(tags, "Image Make")
        model = _exifread_get_str(tags, "Image Model")

    exifread sometimes exposes a tag object whose first element is inside `.values`.
    """

    tag = tags.get(key)
    if not tag:
        return None
    vals = getattr(tag, "values", None)
    if isinstance(vals, (list, tuple)) and vals:
        return _clean(vals[0])
    return _clean(tag)


def _ratio_to_float(x: Any) -> float:
    """Convert exifread Ratio (num/den) or a numeric value to float.

    Use case:
        GPS DMS values are often stored as rational numbers (e.g., 51/1 degrees).
    """

    num = getattr(x, "num", None)
    den = getattr(x, "den", None)
    if num is not None and den not in (None, 0):
        return float(num) / float(den)
    return float(x)


def _dms_to_decimal(dms_tag: Any, ref_tag: Any) -> float:
    """Convert EXIF GPS DMS coordinates to signed decimal degrees.

    Inputs:
        dms_tag: a tag with 3 components: degrees, minutes, seconds
        ref_tag: a tag with N/S/E/W

    Example:
        - Latitude: 40° 26' 46" N  ->  40.446111...
        - Longitude: 79° 58' 56" W -> -79.982222...

    This conversion is necessary because mapping tools and GIS systems typically
    use decimal degrees.
    """

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
    """Build a clickable map URL.

    Use case:
        Many OSINT workflows want a direct link you can paste into a browser.

    Example output:
        http://maps.google.com/?q=37.421999,-122.084057
    """

    return f"http://maps.google.com/?q={lat:.6f},{lon:.6f}"


def extract_record(file_path: str, include_tags: bool) -> Dict[str, Any]:
    """Extract a normalized record from a single file.

    Returned schema (high level):
        {
          "file": "...",
          "exif_present": true/false,
          "captured_with": "Apple iPhone 14" | "Adobe Photoshop" | null,
          "date_taken": "2024:03:01 12:34:56" | null,
          "gps": {"lat": ..., "lon": ..., "map_url": "..."} | null,
          "errors": ["..."]
        }

    Use case:
        This structure is meant to be easy to post-process in scripts, spreadsheets,
        or tools like jq / pandas.
    """

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
            # Use case:
            #   If you plan to do deeper attribution (lens model, serial numbers,
            #   editing software history, etc.), keeping the raw tag text can help.
            out["tags"] = {k: str(v) for k, v in tags.items()}

        make = _exifread_get_str(tags, "Image Make")
        model = _exifread_get_str(tags, "Image Model")
        software = _exifread_get_str(tags, "Image Software")

        # Example:
        #   Make="Apple", Model="iPhone 14" -> "Apple iPhone 14"
        if make or model:
            out["captured_with"] = " ".join([x for x in (make, model) if x])
        else:
            # Fallback example:
            #   Screenshots or edited images often have Software but no Make/Model.
            out["captured_with"] = software

        out["date_taken"] = _first(
            _exifread_get_str(tags, "EXIF DateTimeOriginal"),
            _exifread_get_str(tags, "EXIF DateTimeDigitized"),
            _exifread_get_str(tags, "Image DateTime"),
        )

        # GPS tags (if present) are split into coordinate values and references.
        lat_tag = tags.get("GPS GPSLatitude")
        lat_ref_tag = tags.get("GPS GPSLatitudeRef")
        lon_tag = tags.get("GPS GPSLongitude")
        lon_ref_tag = tags.get("GPS GPSLongitudeRef")

        if lat_tag and lat_ref_tag and lon_tag and lon_ref_tag:
            lat = _dms_to_decimal(lat_tag, lat_ref_tag)
            lon = _dms_to_decimal(lon_tag, lon_ref_tag)

            # Sanity-check range to avoid emitting nonsense coordinates.
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                out["gps"] = {"lat": lat, "lon": lon, "map_url": _map_url(lat, lon)}

    except Exception as e:
        errors.append(str(e))

    return out


def iter_files(input_path: str, extensions: Iterable[str], recursive: bool) -> List[str]:
    """List image files to process.

    Use cases:
        - input_path is a file: return [that file]
        - input_path is a directory: return all matching files
        - recursive=True is useful when you have nested exports (e.g., phone backups)

    Example:
        files = iter_files("./DCIM", [".jpg", ".jpeg"], recursive=True)
    """

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
    """Write records as JSONL (or to stdout if out_path is None).

    Use case:
        JSONL is a good interchange format for large batches and incremental
        processing.

    Example:
        write_jsonl(records, "results.jsonl")
        # then: jq -c 'select(.gps != null)' results.jsonl
    """

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            for obj in records:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    else:
        for obj in records:
            print(json.dumps(obj, ensure_ascii=False))


def main() -> int:
    """CLI entrypoint.

    Examples:
        python3 geolocator.py photo.jpg --pretty
        python3 geolocator.py ./images --jsonl-out out.jsonl

    Tip:
        If you only care about GPS hits when scanning a directory, you can do:

            python3 geolocator.py ./images --jsonl | jq -c 'select(.gps)'
    """

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
    exts = [e.strip() for e in args.extensions.split(";") if e.strip()]

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
