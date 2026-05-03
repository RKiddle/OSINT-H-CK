import exif
import exifread
import os
import sys

# Dependency note: pip install exif exifread

def parse_gps_coordinates(exif_data):
    # Attempt to extract GPS coordinates using exif library
    lat, lon = None, None
    try:
        lat = exif_data.get("GPSLatitude")
        lon = exif_data.get("GPSLongitude")
        if lat and lon:
            lat = convert_rational_to_float(lat)
            lon = convert_rational_to_float(lon)
    except KeyError:
        pass

    # Fallback using exifread if exif library does not provide coordinates
    if lat is None or lon is None:
        lat = extract_from_exifread(exif_data)
        lon = extract_from_exifread(exif_data)

    return lat, lon


def extract_from_exifread(exif_data):
    gps_latitude = exif_data.get('GPSLatitude')
    gps_latitude_ref = exif_data.get('GPSLatitudeRef')
    gps_longitude = exif_data.get('GPSLongitude')
    gps_longitude_ref = exif_data.get('GPSLongitudeRef')

    if gps_latitude and gps_latitude_ref:
        lat = convert_rational_to_float(gps_latitude)
        if gps_latitude_ref.values[0] == 'S':
            lat = -lat
    if gps_longitude and gps_longitude_ref:
        lon = convert_rational_to_float(gps_longitude)
        if gps_longitude_ref.values[0] == 'W':
            lon = -lon
    return lat, lon


def convert_rational_to_float(rational):
    return float(rational[0]) / float(rational[1])


def main():
    # Loading the image
    filename = "Tour3.jpg"
    if not os.path.isfile(filename):
        print(f"File not found: {filename}")
        sys.exit(1)

    # Extracting EXIF data
    with open(filename, 'rb') as image_file:
        tags = exifread.process_file(image_file)
        lat, lon = parse_gps_coordinates(tags)

    # If coordinates are found, create Google Maps link
    if lat is not None and lon is not None:
        print(f"Google Maps URL: http://maps.google.com/?q={{lat:.6f}},{{lon:.6f}}".format(lat=lat, lon=lon))
        sys.exit(0)
    else:
        print("GPS coordinates not found.")
        sys.exit(1)


if __name__ == '__main__':
    main()