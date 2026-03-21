"""
Debug OCR on loot regions. Shows the cropped + processed image so you can
see what Tesseract is receiving.

Usage:
    python3 tools/debug_ocr.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

try:
    import pytesseract
except ImportError:
    print("ERROR: pip3 install pytesseract"); sys.exit(1)

from bot.adb_controller import ADBController
from bot.utils.regions import LOOT_GOLD, LOOT_ELIXIR, LOOT_DARK_ELIXIR

REGIONS = [("LOOT_GOLD", LOOT_GOLD), ("LOOT_ELIXIR", LOOT_ELIXIR), ("LOOT_DARK_ELIXIR", LOOT_DARK_ELIXIR)]


def process(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    # Invert so light text on dark bg becomes dark text on white bg
    inverted = cv2.bitwise_not(gray)
    # Otsu threshold
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Scale up 3x
    h, w = binary.shape
    scaled = cv2.resize(binary, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    return scaled


def main():
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected."); sys.exit(1)

    print("Taking screenshot (make sure a base is visible with loot numbers)...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed."); sys.exit(1)

    h, w = screen.shape[:2]
    print(f"Screen: {w}x{h}\n")

    for name, region in REGIONS:
        px, py, pw, ph = region.to_pixels(w, h)
        crop = screen[py:py+ph, px:px+pw]
        processed = process(crop)

        print(f"{name}  region=({px},{py},{pw},{ph})")
        for psm in (6, 7, 8, 13):
            cfg = f"--psm {psm} --oem 3 -c tessedit_char_whitelist=0123456789,."
            raw = pytesseract.image_to_string(processed, config=cfg).strip()
            cleaned = raw.replace(",", "").replace(".", "").replace(" ", "")
            print(f"  psm={psm}: '{cleaned}'")

        # Save debug images
        cv2.imwrite(f"debug_{name}_crop.png", crop)
        cv2.imwrite(f"debug_{name}_processed.png", processed)

    print("\nSaved debug_LOOT_*.png — open them to check if the region/text looks right.")


if __name__ == "__main__":
    main()
