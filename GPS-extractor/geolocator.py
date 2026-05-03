import os
import json
import exifread
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Function to get GPS coordinates

def get_gps_coordinates(exif):
    gps_latitude = exif.get('GPS GPSLatitude')
    gps_longitude = exif.get('GPS GPSLongitude')
    if gps_latitude and gps_longitude:
        lat_ref = exif.get('GPS GPSLatitudeRef')
        lon_ref = exif.get('GPS GPSLongitudeRef')

        latitude = convert_to_degrees(gps_latitude) * (1 if lat_ref == 'N' else -1)
        longitude = convert_to_degrees(gps_longitude) * (1 if lon_ref == 'E' else -1)
        return latitude, longitude
    return None, None

# Helper function to convert GPS coordinates

def convert_to_degrees(value):
    d = float(value[0].num) / float(value[0].den)
    m = float(value[1].num) / float(value[1].den)
    s = float(value[2].num) / float(value[2].den)
    return d + (m / 60.0) + (s / 3600.0)

# Main function to extract EXIF data

def extract_exif_data(file_path):
    errors = []
    data = {'errors': errors}
    try:
        with open(file_path, 'rb') as f:
            exif = exifread.process_file(f, stop_tag='GPSLatitude')

            # Extracting relevant EXIF data
            data['captured_with'] = f"{exif.get('Image Make', 'Unknown')} {exif.get('Image Model', 'Unknown')}" or exif.get('Image Software', 'Unknown')
            data['date_taken'] = exif.get('EXIF DateTimeOriginal') or exif.get('EXIF DateTimeDigitized') or exif.get('Image DateTime')
            lat, lon = get_gps_coordinates(exif)
            data['gps'] = {'latitude': lat, 'longitude': lon, 'map_url': f'http://maps.google.com/?q={{lat:.6f}},{{lon:.6f}}' if lat is not None and lon is not None else None}
    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")
        errors.append(str(e))

    return data

# Directory processing

def process_directory(directory):
    results = []
    for filename in os.listdir(directory):
        if filename.endswith(('.jpg', '.jpeg', '.png')):  # Add your allowed extensions here
            file_path = os.path.join(directory, filename)
            exif_data = extract_exif_data(file_path)
            results.append(exif_data)
    return results

# Set tool to 'exifread'
# Handle JSONL output

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Extract EXIF data from images.')
    parser.add_argument('directory', help='Directory to scan for images')
    parser.add_argument('--jsonl', action='store_true', help='Output in JSONL format')
    args = parser.parse_args()

    results = process_directory(args.directory)

    if args.jsonl:
        for result in results:
            print(json.dumps(result))
    else:
        print(json.dumps(results, indent=4))
