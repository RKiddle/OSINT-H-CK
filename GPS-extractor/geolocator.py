# JSON Output Schema
# Output JSON structure:
# {
#   "file": "input path",
#   "exif_present": true or false,
#   "captured_with": "camera make/model or null",
#   "date_taken": "date string or null",
#   "gps": {
#     "lat": "latitude or null",
#     "lon": "longitude or null",
#     "map_url": "http://maps.google.com/?q={lat:.6f},{lon:.6f} or null"
#   },
#   "errors": ["array of error messages"],
#   "tool": "exif or exifread"
# }

import sys
import json
import os
import exifread

# Add your GPS extraction logic here.

def extract_gps(exif_data):
    # Dummy implementation, replace with actual extraction logic
    return {'lat': 0.0, 'lon': 0.0, 'map_url': 'http://maps.google.com/?q={lat:.6f},{lon:.6f}'}  # Replace with actual values

if __name__ == '__main__':
    input_path = sys.argv[1]
    json_output = True
    pretty_output = False
    # Process command line arguments for --json and --pretty

    try:
        if not os.path.exists(input_path):
            print(json.dumps({'file': input_path, 'exif_present': False, 'captured_with': None, 'date_taken': None, 'gps': None, 'errors': ["File not found."], 'tool': 'exif'}))
            exit(2)

        with open(input_path, 'rb') as f:
            tags = exifread.process_file(f)
            # Check for presence of EXIF data and extract required fields
            exif_present = True  # Update this based on extraction logic
            captured_with = tags.get('EXIF ImageWidth', None)  # Replace with actual tag for camera
            date_taken = tags.get('EXIF DateTimeOriginal', None)  # Replace with actual logic to extract date
            gps = extract_gps(tags)  # Extract GPS data
            errors = []  # Collect errors if any

        output_data = {
            'file': input_path,
            'exif_present': exif_present,
            'captured_with': str(captured_with),
            'date_taken': str(date_taken),
            'gps': gps,
            'errors': errors,
            'tool': 'exif'
        }

        if json_output:
            if pretty_output:
                print(json.dumps(output_data, indent=4))
            else:
                print(json.dumps(output_data))
            if gps['lat'] and gps['lon']:
                exit(0)
            else:
                exit(1)

    except Exception as e:
        print(json.dumps({'file': input_path, 'exif_present': False, 'captured_with': None, 'date_taken': None, 'gps': None, 'errors': [str(e)], 'tool': 'exif'}))
        exit(3)