import exifread
import os
import json
import argparse

def extract_exif(file_path):
    with open(file_path, 'rb') as f:
        tags = exifread.process_file(f, stop_tag=None)
    # Extract required EXIF data
    gps_lat = tags.get('GPS GPSLatitude')
    gps_lat_ref = tags.get('GPS GPSLatitudeRef')
    gps_lon = tags.get('GPS GPSLongitude')
    gps_lon_ref = tags.get('GPS GPSLongitudeRef')
    
    if gps_lat and gps_lon:
        lat = float(gps_lat.displayValue) if gps_lat_ref == 'N' else -float(gps_lat.displayValue)
        lon = float(gps_lon.displayValue) if gps_lon_ref == 'E' else -float(gps_lon.displayValue)
        map_url = f'http://maps.google.com/?q={lat:.6f},{lon:.6f}'
    else:
        lat, lon, map_url = None, None, None
    
    return {
        'file': file_path,
        'exif_present': bool(tags),
        'captured_with': tags.get('Image Make', '') + ' ' + tags.get('Image Model', ''),
        'date_taken': tags.get('EXIF DateTimeOriginal', '') or tags.get('Image DateTime', ''),
        'gps': {'lat': lat, 'lon': lon, 'map_url': map_url},
        'errors': [],
        'tool': 'exifread',
        'tags': {tag: str(tags[tag]) for tag in tags.keys() if 'JPEG' in tag}
    }

def process_directory(directory, extensions, recursive=True):
    results = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            if any(file_name.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file_name)
                results.append(extract_exif(file_path))
        if not recursive:
            break
    return results

def save_jsonl(results, jsonl_out):
    with open(jsonl_out, 'w') as f:
        for result in results:
            f.write(json.dumps(result) + '\n')

def main():
    parser = argparse.ArgumentParser(description='EXIF metadata extractor')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('--no-recursive', action='store_true', help='Disable recursive scanning')
    parser.add_argument('--extensions', nargs='+', default=['.jpg', '.jpeg', '.png'], help='Filtered file extensions')
    parser.add_argument('--jsonl', action='store_true', help='Output in JSONL format')
    parser.add_argument('--jsonl-out', type=str, help='Output file for JSONL')
    parser.add_argument('--include-tags', action='store_true', help='Include raw EXIF tags')
    args = parser.parse_args()

    if os.path.isdir(args.input):
        results = process_directory(args.input, args.extensions, not args.no_recursive)
    else:
        results = [extract_exif(args.input)]

    if args.jsonl:
        if args.jsonl_out:
            save_jsonl(results, args.jsonl_out)
        else:
            print(json.dumps(results, indent=2))

    # Exit code logic
    exit_code = 0
    if all(r['gps']['lat'] is None and r['gps']['lon'] is None for r in results):
        exit_code = 2 if len(results) > 0 else 3
    elif any(r['gps']['lat'] is not None for r in results):
        exit_code = 0
    else:
        exit_code = 1
    exit(exit_code)

if __name__ == '__main__':
    main()