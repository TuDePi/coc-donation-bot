"""
Region calibration tool.
Captures a screenshot from the device, lets you draw rectangles,
and prints the Region(...) ratio values for regions.py.

Usage:
    python3 tools/calibrate_regions.py

Controls:
    - Click and drag to draw a rectangle
    - Press ENTER or SPACE to confirm and name the region
    - Press ESC to quit
    - Press U to undo the last region
"""

import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from bot.adb_controller import ADBController

# --- state ---
drawing = False
start_x = start_y = 0
end_x = end_y = 0
regions = []       # list of (name, x1, y1, x2, y2)
current_rect = None
base_image = None
display_image = None


def redraw():
    global display_image
    display_image = base_image.copy()
    for name, x1, y1, x2, y2 in regions:
        cv2.rectangle(display_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(display_image, name, (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    if current_rect:
        cx1, cy1, cx2, cy2 = current_rect
        cv2.rectangle(display_image, (cx1, cy1), (cx2, cy2), (0, 120, 255), 2)
    cv2.imshow("Region Calibrator  —  drag to select, ENTER to name, U to undo, ESC to quit", display_image)


def mouse_cb(event, x, y, flags, param):
    global drawing, start_x, start_y, end_x, end_y, current_rect

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y
        current_rect = None

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        current_rect = (min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y))
        redraw()

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_x, end_y = x, y
        current_rect = (min(start_x, end_x), min(start_y, end_y),
                        max(start_x, end_x), max(start_y, end_y))
        redraw()


def print_summary(w, h):
    print("\n" + "=" * 60)
    print("Paste these into bot/utils/regions.py:")
    print("=" * 60)
    for name, x1, y1, x2, y2 in regions:
        rx = x1 / w
        ry = y1 / h
        rw = (x2 - x1) / w
        rh = (y2 - y1) / h
        print(f"{name.upper()} = Region({rx:.3f}, {ry:.3f}, {rw:.3f}, {rh:.3f})")
    print("=" * 60)


def main():
    global base_image, display_image, current_rect

    print("Connecting to device...")
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected. Connect via USB and enable USB debugging.")
        sys.exit(1)

    print("Taking screenshot...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed.")
        sys.exit(1)

    h, w = screen.shape[:2]
    print(f"Screen: {w}x{h}")
    print("\nInstructions:")
    print("  1. Drag a rectangle around a loot number (gold, elixir, etc.)")
    print("  2. Press ENTER or SPACE to name it (type in terminal, press Enter)")
    print("  3. Repeat for each region you need")
    print("  4. Press ESC when done\n")

    base_image = screen.copy()
    display_image = base_image.copy()

    cv2.namedWindow("Region Calibrator  —  drag to select, ENTER to name, U to undo, ESC to quit",
                    cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Region Calibrator  —  drag to select, ENTER to name, U to undo, ESC to quit",
                     min(w, 1280), min(h, 720))
    cv2.setMouseCallback("Region Calibrator  —  drag to select, ENTER to name, U to undo, ESC to quit",
                         mouse_cb)
    redraw()

    while True:
        key = cv2.waitKey(50) & 0xFF

        if key == 27:  # ESC — quit
            break

        elif key in (13, 32) and current_rect:  # ENTER or SPACE — confirm region
            x1, y1, x2, y2 = current_rect
            if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
                print("Rectangle too small, try again.")
                continue
            name = input(f"Name this region [{x1},{y1} → {x2},{y2}]: ").strip()
            if not name:
                name = f"region_{len(regions) + 1}"
            regions.append((name, x1, y1, x2, y2))
            current_rect = None
            redraw()
            print(f"  Saved '{name}'")

        elif key == ord('u') and regions:  # U — undo
            removed = regions.pop()
            print(f"  Undone: {removed[0]}")
            current_rect = None
            redraw()

    cv2.destroyAllWindows()

    if regions:
        print_summary(w, h)
    else:
        print("No regions saved.")


if __name__ == "__main__":
    main()
