import os
import json
import argparse
from typing import List, Dict, Any, Optional


def extract_exif_data(file_path: str) -> Dict[str, Any]:
    """Extract EXIF data from an image file."""
    # Implementation of EXIF extraction using exif or exifread
    pass  # Replace with actual logic


def process_file(file_path: str) -> Dict[str, Any]:
    """Process a single file and extract EXIF data."""
    exif_data = extract_exif_data(file_path)
    # Populate the result dictionary with required fields
    result = {
        'file': file_path,
        'exif_present': bool(exif_data),
        'captured_with': exif_data.get('make_and_model', None),
        'date_taken': exif_data.get('DateTimeOriginal', exif_data.get('DateTimeDigitized', None)),
        'gps': {
            'lat': exif_data.get('lat'),
            'lon': exif_data.get('lon'),
            'map_url': f'http://maps.google.com/?q={{lat:.6f}},{{lon:.6f}}' if exif_data.get('lat') and exif_data.get('lon') else None
        },
        'errors': [],
        'tool': 'exif' if 'exif' in exif_data else 'exifread',
    }
    return result


def process_directory(directory: str, extensions: List[str], recursive: bool) -> List[Dict[str, Any]]:
    """Process all images in a directory."""
    results = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                result = process_file(file_path)
                results.append(result)
        if not recursive:
            break
    return results


def main():
    parser = argparse.ArgumentParser(description='EXIF Metadata Extractor')
    parser.add_argument('input', help='Single file or directory to process')
    parser.add_argument('--jsonl', action='store_true', help='Output JSONL format (one object per line)')
    parser.add_argument('--pretty', action='store_true', help='Pretty print the JSON output')
    parser.add_argument('--extensions', type=str, default='.jpg,.jpeg,.png,.tif,.tiff,.heic', help='Comma separated list of image extensions to process')
    parser.add_argument('--no-recursive', action='store_true', help='Don’t recurse into subdirectories')
    args = parser.parse_args()

    input_path = args.input
    extensions = args.extensions.split(',')
    if os.path.isdir(input_path):
        results = process_directory(input_path, extensions, not args.no_recursive)
    elif os.path.isfile(input_path):
        results = [process_file(input_path)]
    else:
        print('Error: File or directory not found.')
        exit(2)

    if args.jsonl:
        for result in results:
            print(json.dumps(result))
    else:
        print(json.dumps(results, indent=4) if args.pretty else json.dumps(results))


if __name__ == '__main__':
    main()