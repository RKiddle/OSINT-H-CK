"""Extract GPS coordinates from an image's EXIF metadata.

This script reads GPS latitude/longitude stored in EXIF as DMS (degrees, minutes,
seconds) plus a reference (N/S/E/W) and converts them into decimal degrees.

Dependencies:
  pip install exif exifread

Usage:
  python geolocator.py path/to/image.jpg

Exit codes:
  0  GPS coordinates found
  1  No GPS coordinates (or no EXIF)
  2  File not found
  3  Could not read/parse EXIF data

Notes / edge cases handled:
  - Works with either `exif` (fast/simple) OR falls back to `exifread` (more compatible).
  - EXIF GPS components are often rationals; this script converts them safely to float.
  - Missing or unexpected GPS references (lat_ref/lon_ref) are treated as \"no GPS\".
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import exifread

try:
    from exif import Image as ExifImage  # type: ignore
except Exception:  # pragma: no cover
    ExifImage = None  # type: ignore

def _to_float(value: Any) -> float:
    """Convert EXIF number/rational-like values to float."""
    try:
        return float(value)
    except Exception:
        numerator = getattr(value, "numerator", None)
        denominator = getattr(value, "denominator", None)
        if numerator is not None and denominator not in (None, 0):
            return float(numerator) / float(denominator)
        raise

def _exifread_ratio_to_float(x: Any) -> float:
    """Convert an exifread Ratio (or similar) to float."""
    # exifread.utils.Ratio typically has num/den
    num = getattr(x, "num", None)
    den = getattr(x, "den", None)
    if num is not None and den not in (None, 0):
        return float(num) / float(den)
    # sometimes it's already numeric
    return float(x)

def convert_to_decimal(coords: Iterable[Any], reference: str) -> float:
    """Convert EXIF GPS DMS coords to decimal degrees."""
    dms = list(coords)
    if len(dms) != 3:
        raise ValueError(f"Expected 3 DMS components, got {len(dms)}")

    degrees, minutes, seconds = dms
    decimal_degrees = (
        _to_float(degrees) + (_to_float(minutes) / 60.0) + (_to_float(seconds) / 3600.0)
    )

    ref = (reference or "").strip().upper()
    if ref in {"S", "W"}:
        decimal_degrees = -decimal_degrees
    elif ref in {"N", "E"}:
        pass
    else:
        raise ValueError(f"Unexpected GPS reference: {reference!r}")

    return decimal_degrees

def _convert_exifread_dms_to_decimal(dms_values: Any, ref_value: Any) -> float:
    """Convert exifread GPS DMS tag values + ref tag to decimal degrees."""
    # exifread provides tag.values which is usually [Ratio, Ratio, Ratio]
    dms = list(getattr(dms_values, "values", dms_values))
    if len(dms) != 3:
        raise ValueError(f"Expected 3 DMS components, got {len(dms)}")

    degrees, minutes, seconds = dms
    decimal_degrees = (
        _exifread_ratio_to_float(degrees)
        + (_exifread_ratio_to_float(minutes) / 60.0)
        + (_exifread_ratio_to_float(seconds) / 3600.0)
    )

    ref = str(getattr(ref_value, "values", [ref_value])[0]).strip().upper()
    if ref in {"S", "W"}:
        decimal_degrees = -decimal_degrees
    elif ref in {"N", "E"}:
        pass
    else:
        raise ValueError(f"Unexpected GPS reference: {ref!r}")

    return decimal_degrees

def extract_gps_exif(image_path: Path) -> Optional[Tuple[float, float]]:
    """Try extracting GPS using the `exif` library (if available)."""
    if ExifImage is None:
        return None

    with image_path.open("rb") as image_file:
        img = ExifImage(image_file)

    if not getattr(img, "has_exif", False):
        return None

    required = (
        "gps_latitude",
        "gps_latitude_ref",
        "gps_longitude",
        "gps_longitude_ref",
    )
    if not all(hasattr(img, attr) for attr in required):
        return None

    lat = convert_to_decimal(img.gps_latitude, img.gps_latitude_ref)
    lon = convert_to_decimal(img.gps_longitude, img.gps_longitude_ref)

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    return lat, lon

def extract_gps_exifread(image_path: Path) -> Optional[Tuple[float, float]]:
    """Extract GPS using exifread (more compatible with varied JPEGs)."""
    with image_path.open("rb") as f:
        tags = exifread.process_file(f, details=False)

    # exifread uses keys like 'GPS GPSLatitude'
    lat_tag = tags.get("GPS GPSLatitude")
    lat_ref_tag = tags.get("GPS GPSLatitudeRef")
    lon_tag = tags.get("GPS GPSLongitude")
    lon_ref_tag = tags.get("GPS GPSLongitudeRef")

    if not (lat_tag and lat_ref_tag and lon_tag and lon_ref_tag):
        return None

    lat = _convert_exifread_dms_to_decimal(lat_tag, lat_ref_tag)
    lon = _convert_exifread_dms_to_decimal(lon_tag, lon_ref_tag)

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    return lat, lon

def extract_gps(image_path: Path) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) if present, otherwise None."""
    # First try the original library
    result = extract_gps_exif(image_path)
    if result is not None:
        return result

    # Fallback
    return extract_gps_exifread(image_path)

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python geolocator.py <path_to_image>", file=sys.stderr)
        return 3

    image_path = Path(argv[1])

    if not image_path.exists():
        print(f"Error: Could not find the file at '{image_path}'", file=sys.stderr)
        return 2

    try:
        result = extract_gps(image_path)
    except Exception as e:
        print(f"Error reading EXIF/GPS data: {e}", file=sys.stderr)
        return 3

    if result is None:
        print("No GPS coordinates found.")
        return 1

    lat, lon = result
    print("--- GPS DATA FOUND ---")
    print(f"Latitude:  {lat:.6f}")
    print(f"Longitude: {lon:.6f}")
    print(f"Google Maps Link: http://maps.google.com/?q={lat:.6f},{lon:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))