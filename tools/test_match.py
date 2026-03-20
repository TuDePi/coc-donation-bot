#!/usr/bin/env python3
"""
Test if a template matches the current device screen.

Usage:
    python tools/test_match.py <template_path> [threshold]
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from bot.adb_controller import ADBController
from bot.vision import Vision


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/test_match.py <template_path> [threshold]")
        print("Example: python tools/test_match.py templates/ui/attack_button.png 0.8")
        sys.exit(1)

    template_path = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.80

    if not os.path.exists(template_path):
        print(f"ERROR: Template not found: {template_path}")
        sys.exit(1)

    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected.")
        sys.exit(1)

    print("Taking screenshot...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Failed to take screenshot")
        sys.exit(1)

    vision = Vision(templates_dir=".")
    match = vision.find_template(screen, template_path, threshold=threshold)

    if match:
        x, y, confidence = match
        print(f"MATCH FOUND: center=({x}, {y}), confidence={confidence:.4f}")

        # Draw the match on screen for visual verification
        template = cv2.imread(template_path)
        th, tw = template.shape[:2]
        top_left = (x - tw // 2, y - th // 2)
        bottom_right = (x + tw // 2, y + th // 2)
        display = screen.copy()
        cv2.rectangle(display, top_left, bottom_right, (0, 255, 0), 3)
        cv2.circle(display, (x, y), 5, (0, 0, 255), -1)

        # Scale for display
        h, w = display.shape[:2]
        if w > 1200:
            scale = 1200 / w
            display = cv2.resize(display, (int(w * scale), int(h * scale)))

        cv2.imshow("Match Result (press any key to close)", display)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print(f"NO MATCH (threshold={threshold})")

        # Show all matches at various thresholds for debugging
        vision2 = Vision(templates_dir=".")
        for t in [0.7, 0.6, 0.5]:
            m = vision2.find_template(screen, template_path, threshold=t)
            if m:
                print(f"  Would match at threshold={t}: confidence={m[2]:.4f}")
                break
        else:
            print("  No match even at threshold=0.5")


if __name__ == "__main__":
    main()
