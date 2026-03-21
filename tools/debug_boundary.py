"""
Debug boundary/red zone detection.
Shows what the bot detects as the deployment boundary.

Usage:
    python3 tools/debug_boundary.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from bot.adb_controller import ADBController

def main():
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected."); sys.exit(1)

    print("Taking screenshot (enemy base should be visible)...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed."); sys.exit(1)

    h, w = screen.shape[:2]
    print(f"Screen: {w}x{h}")

    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)

    # Try multiple HSV ranges for the orange/red boundary
    ranges = [
        ("orange_tight",  [8, 180, 180],  [22, 255, 255]),
        ("orange_wide",   [5, 150, 150],  [25, 255, 255]),
        ("red_low",       [0, 150, 150],  [10, 255, 255]),
        ("red_high",      [170, 150, 150],[180, 255, 255]),
        ("yellow_orange", [10, 100, 150], [30, 255, 255]),
    ]

    out = screen.copy()

    for name, low, high in ranges:
        mask = cv2.inRange(hsv, np.array(low), np.array(high))

        # Black out HUD
        mask[:int(h * 0.08), :] = 0
        mask[int(h * 0.82):, :] = 0
        mask[:, :int(w * 0.08)] = 0
        mask[:, int(w * 0.85):] = 0
        mask[int(h * 0.75):, :int(w * 0.20)] = 0

        white_pixels = cv2.countNonZero(mask)
        cv2.imwrite(f"debug_boundary_{name}.png", mask)
        print(f"  {name}: {white_pixels} white pixels  HSV {low} -> {high}")

        # Find contours
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(mask, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)
            print(f"    Largest contour area: {area}  ({len(contours)} contours total)")

    # Also save a combined visualization
    # Show all orange-ish pixels overlaid on the screenshot
    combined_mask = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([30, 255, 255]))
    combined_mask[:int(h * 0.08), :] = 0
    combined_mask[int(h * 0.82):, :] = 0
    combined_mask[:, :int(w * 0.08)] = 0
    combined_mask[:, int(w * 0.85):] = 0
    combined_mask[int(h * 0.75):, :int(w * 0.20)] = 0

    # Overlay in red on screenshot
    overlay = screen.copy()
    overlay[combined_mask > 0] = [0, 0, 255]
    blended = cv2.addWeighted(screen, 0.6, overlay, 0.4, 0)
    cv2.imwrite("debug_boundary_overlay.png", blended)

    print(f"\nSaved debug_boundary_overlay.png — red highlights show all detected orange/red pixels")
    print("Saved debug_boundary_<name>.png masks for each HSV range")
    print("\nOpen debug_boundary_overlay.png to see what's being detected.")


if __name__ == "__main__":
    main()
