"""
Test troop deployment detection.
Takes a screenshot and checks which troops are visible in the troop bar,
simulates the deploy loop logic (without actually tapping).

Run while on an attack screen with troops visible in the bar.

Usage:
    python3 tools/test_deploy.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.config_loader import load_config


def main():
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected."); sys.exit(1)

    print("Taking screenshot (troops should be visible in the bottom bar)...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed."); sys.exit(1)

    h, w = screen.shape[:2]
    print(f"Screen: {w}x{h}\n")

    config = load_config("config.yaml")
    threshold = config.vision.default_threshold if hasattr(config.vision, "default_threshold") else 0.80
    overrides = vars(config.vision.overrides) if hasattr(config.vision, "overrides") and config.vision.overrides else {}
    vision = Vision(templates_dir="templates", default_threshold=threshold, threshold_overrides=overrides)

    army_config = vars(config.training.army)
    if not army_config:
        print("No army configured in config.training.army")
        return

    print(f"Army config: {army_config}\n")
    print("Scanning troop bar...\n")

    out = screen.copy()
    found_any = False

    for troop_name in army_config:
        template_path = f"troops/{troop_name}.png"
        match = vision.find_template(screen, template_path)

        if match:
            x, y, conf = match
            found_any = True

            # Check saturation to detect grayed-out (depleted) icon
            size = 25
            x1, y1 = max(0, x - size), max(0, y - size)
            x2, y2 = min(w, x + size), min(h, y + size)
            crop = screen[y1:y2, x1:x2]
            import numpy as np
            hsv_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            mean_sat = float(np.mean(hsv_crop[:, :, 1]))
            depleted = mean_sat < 40

            print(f"  FOUND  {troop_name}")
            print(f"         position=({x}, {y})  confidence={conf:.3f}")
            print(f"         saturation={mean_sat:.1f}  {'DEPLETED (x0)' if depleted else 'AVAILABLE'}")
            print(f"         template: templates/{template_path}")

            # Draw on output
            cv2.circle(out, (x, y), 30, (0, 255, 0), 3)
            cv2.putText(out, troop_name, (x - 20, y - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            print(f"  MISSING  {troop_name}")
            print(f"           template: templates/{template_path}")
            full_path = os.path.join("templates", template_path)
            if not os.path.exists(full_path):
                print(f"           FILE NOT FOUND — capture it with:")
                print(f"           python3 tools/capture_template.py templates/{template_path}")
            else:
                # Try with lower threshold to see if it's a threshold issue
                low_match = vision.find_template(screen, template_path, threshold=0.5)
                if low_match:
                    print(f"           Found at threshold 0.50: conf={low_match[2]:.3f}")
                    print(f"           Current threshold is too high. Add override in config.yaml:")
                    print(f"           vision.overrides.{troop_name}: {low_match[2] - 0.05:.2f}")
                else:
                    print(f"           Not found even at 0.50 — template may need recapture")
        print()

    # Also check for any troop icons not in config
    print("--- Checking hero icons ---\n")
    for hero in ["king", "queen", "warden", "champion"]:
        template_path = f"troops/{hero}.png"
        full_path = os.path.join("templates", template_path)
        if not os.path.exists(full_path):
            print(f"  {hero}: no template (templates/{template_path})")
            continue
        match = vision.find_template(screen, template_path)
        if match:
            x, y, conf = match
            print(f"  FOUND  {hero}  at ({x},{y})  conf={conf:.3f}")
            cv2.circle(out, (x, y), 30, (255, 165, 0), 3)
            cv2.putText(out, hero, (x - 20, y - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
        else:
            print(f"  {hero}: not found on screen")

    cv2.imwrite("debug_troop_bar.png", out)
    print(f"\nSaved debug_troop_bar.png — green = army troops, orange = heroes")

    if not found_any:
        print("\n*** No troops found! Make sure you have:")
        print("    1. Troop templates captured in templates/troops/")
        print("    2. The attack screen is open with troops in the bar")
        print("    3. Capture templates with: python3 tools/capture_template.py templates/troops/<name>.png")


if __name__ == "__main__":
    main()
