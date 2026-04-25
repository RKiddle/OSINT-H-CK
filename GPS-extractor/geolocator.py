#### pip install exif

import sys
from exif import Image

def convert_to_decimal(coords, reference):
    """
    Converts EXIF GPS format (Degrees, Minutes, Seconds) 
    into Decimal Degrees for Google Maps.
    """
    # coordinates come as a tuple: (degrees, minutes, seconds)
    decimal_degrees = coords[0] + (coords[1] / 60.0) + (coords[2] / 3600.0)
    
    # South and West coordinates must be negative in decimal format
    if reference == "S" or reference == "W":
        decimal_degrees = -decimal_degrees
        
    return decimal_degrees

def extract_gps(image_path):
    try:
        with open(image_path, 'rb') as image_file:
            img = Image(image_file)
    except FileNotFoundError:
        print(f"Error: Could not find the file at '{image_path}'")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Check if the image has any metadata at all
    if not img.has_exif:
        print("no GPS coordinates (No EXIF data found)")
        return

    # Try to extract the specific GPS tags
    try:
        if hasattr(img, 'gps_latitude') and hasattr(img, 'gps_longitude'):
            # Fetch coordinates and their directional references (N/S, E/W)
            lat = convert_to_decimal(img.gps_latitude, img.gps_latitude_ref)
            lon = convert_to_decimal(img.gps_longitude, img.gps_longitude_ref)

            print("--- GPS DATA FOUND ---")
            print(f"Latitude:  {lat:.6f}")
            print(f"Longitude: {lon:.6f}")
            print(f"Google Maps Link: https://www.google.com/maps?q={lat},{lon}")
        else:
            print("no GPS coordinates")
    except Exception as e:
        print("no GPS coordinates")

if __name__ == "__main__":
    # Ensure the user provided a file path as an argument
    if len(sys.argv) != 2:
        print("Usage: python geolocator.py <path_to_image>")
    else:
        extract_gps(sys.argv[1])


"""
How to Run It
Open your terminal or command prompt, navigate to the folder where you saved geolocator.py, and pass an image file as an argument.

If the image has no location data:

Bash
$ python geolocator.py vacation_photo_stripped.jpg
no GPS coordinates
If the image contains location data:

Bash
$ python geolocator.py vacation_photo_original.jpg
--- GPS DATA FOUND ---
Latitude:  48.858370
Longitude: 2.294481
Google Maps Link: https://www.google.com/maps?q=48.858370,2.294481
How the Magic Works
Cameras and smartphones do not save GPS coordinates as standard decimals (like 48.858370). 
Instead, they save them in the EXIF data as a tuple of Degrees, Minutes, and Seconds (DMS), along with a compass reference (North, South, East, West).

The convert_to_decimal function in the script does the necessary math to convert that DMS format into the Decimal Degree format that Google Maps requires to drop a pin. 
It also checks if the coordinate is South or West, and if so, turns the number negative, which is the standard geographic formatting rule.
"""
