import csv
import numpy as np
from PIL import Image

CSV_FILE = "frame_colors.csv"
OUTPUT_IMAGE = "movie_palette_resized.png"

IMAGE_HEIGHT = 1200
STRIPE_WIDTH = 2
OUTPUT_MAX_WIDTH = 8000   # Safe for all image viewers


def read_colors(csv_file):
    colors = []
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            colors.append([int(row["R"]), int(row["G"]), int(row["B"])])
    return np.array(colors, dtype=np.uint8)


def make_palette_image(colors, stripe_width, height):
    stripes = np.repeat(colors, stripe_width, axis=0)
    img_array = np.tile(stripes[np.newaxis, :, :], (height, 1, 1))
    return img_array


def main():
    print("Loading CSV...")
    colors = read_colors(CSV_FILE)

    print("Creating large poster array...")
    arr = make_palette_image(colors, STRIPE_WIDTH, IMAGE_HEIGHT)

    print(f"Original size: {arr.shape[1]}×{arr.shape[0]} pixels")

    # Create PIL image
    img = Image.fromarray(arr, mode="RGB")

    # If too large, downscale
    if arr.shape[1] > OUTPUT_MAX_WIDTH:
        scale = OUTPUT_MAX_WIDTH / arr.shape[1]
        new_width = int(arr.shape[1] * scale)
        new_height = int(arr.shape[0])
        print(f"Resizing to: {new_width}×{new_height}")
        img = img.resize((new_width, new_height), Image.LANCZOS)

    print("Saving...")
    img.save(OUTPUT_IMAGE, "PNG")
    print(f"Saved to {OUTPUT_IMAGE}")


if __name__ == "__main__":
    main()
