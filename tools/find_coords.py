#!/usr/bin/env python3
"""
Click on the screenshot to see coordinates. Use this to find button positions.

Usage:
    python tools/find_coords.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from bot.adb_controller import ADBController


def main():
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected.")
        sys.exit(1)

    print("Taking screenshot...")
    image = adb.screenshot()
    if image is None:
        print("ERROR: Failed to take screenshot")
        sys.exit(1)

    h, w = image.shape[:2]
    print(f"Device resolution: {w}x{h}")

    # Scale for display
    scale = 1.0
    if w > 1200:
        scale = 1200 / w
    display = cv2.resize(image, (int(w * scale), int(h * scale)))

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            # Convert back to device coordinates
            dev_x = int(x / scale)
            dev_y = int(y / scale)
            ratio_x = dev_x / w
            ratio_y = dev_y / h
            print(f"  Device coords: ({dev_x}, {dev_y})  |  Ratio: ({ratio_x:.3f}, {ratio_y:.3f})")

    window = "Click to get coordinates (ESC to quit)"
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window, on_click)

    print("\nClick on the CHAT BUTTON and note the ratio values.")
    print("Press ESC to quit.\n")

    while True:
        cv2.imshow(window, display)
        if cv2.waitKey(30) & 0xFF == 27:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
