"""
Finds the right scale factor for building templates against the current screen.
Run while an enemy base is visible.

Usage:
    python3 tools/find_building_scale.py
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from bot.adb_controller import ADBController

TEMPLATES_DIR = "templates/buildings"
SCALES = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]
THRESHOLD = 0.55  # lower than normal to catch weak matches


def try_match(gray_screen, template_path, scale):
    tmpl = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if tmpl is None:
        return None, 0
    h, w = tmpl.shape
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    if new_w > gray_screen.shape[1] or new_h > gray_screen.shape[0]:
        return None, 0
    resized = cv2.resize(tmpl, (new_w, new_h), interpolation=cv2.INTER_AREA)
    result = cv2.matchTemplate(gray_screen, resized, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return max_loc, max_val


def main():
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected."); sys.exit(1)

    print("Taking screenshot (make sure enemy base is visible)...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed."); sys.exit(1)

    gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    print(f"Screen: {w}x{h}\n")

    templates = sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.png")))
    if not templates:
        print(f"No templates found in {TEMPLATES_DIR}"); sys.exit(1)

    print(f"Testing {len(templates)} templates across {len(SCALES)} scales...\n")

    best_overall = []

    for tmpl_path in templates:
        name = os.path.basename(tmpl_path)
        best_val = 0
        best_scale = 0
        best_loc = None

        for scale in SCALES:
            loc, val = try_match(gray, tmpl_path, scale)
            if val > best_val:
                best_val = val
                best_scale = scale
                best_loc = loc

        if best_val >= THRESHOLD:
            best_overall.append((best_val, best_scale, best_loc, name))
            print(f"  MATCH  {name}")
            print(f"         scale={best_scale:.2f}  conf={best_val:.3f}  loc={best_loc}")

    if not best_overall:
        print("No matches found above threshold 0.55 at any scale.")
        print("The assets may not match this game version/skin.")
        return

    best_overall.sort(reverse=True)
    scales = [s for _, s, _, _ in best_overall]
    avg_scale = sum(scales) / len(scales)
    print(f"\nBest matching scale: {avg_scale:.3f}  (add to config.yaml as building_template_scale)")
    print(f"Top match: {best_overall[0][3]} at scale={best_overall[0][1]:.2f} conf={best_overall[0][0]:.3f}")

    # Save annotated screenshot
    out = screen.copy()
    for val, scale, loc, name in best_overall[:10]:
        tmpl = cv2.imread(os.path.join(TEMPLATES_DIR, name), cv2.IMREAD_GRAYSCALE)
        th = int(tmpl.shape[0] * scale)
        tw = int(tmpl.shape[1] * scale)
        cv2.rectangle(out, loc, (loc[0]+tw, loc[1]+th), (0,255,0), 2)
        cv2.putText(out, f"{name[:20]} {val:.2f}", (loc[0], loc[1]-4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
    cv2.imwrite("debug_building_matches.png", out)
    print("\nSaved debug_building_matches.png — open it to verify matches.")


if __name__ == "__main__":
    main()
