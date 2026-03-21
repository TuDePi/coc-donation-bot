"""
Visualize color-based building detection on a live screenshot.
Run while an enemy base is visible.

Usage:
    python3 tools/debug_color_detect.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from bot.adb_controller import ADBController
from bot.actions.attacker import Attacker
from bot.vision import Vision
from bot.actions.navigator import Navigator


def main():
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected."); sys.exit(1)

    print("Taking screenshot...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed."); sys.exit(1)

    h, w = screen.shape[:2]
    print(f"Screen: {w}x{h}")

    # Reuse attacker's detection logic directly
    vision = Vision()

    class FakeConfig:
        class safety: dry_run = True
        class attack:
            deploy_strategy = "targeted"
            deploy_side = "bottom"
            use_heroes = False
            hero_deploy_delay = 5
            spell_deploy_delay = 1.0
            max_searches = 50
            class min_loot:
                gold = 0; elixir = 0; dark_elixir = 0
        class training:
            class army: pass
            class spells: pass

    attacker = Attacker(adb, vision, None, FakeConfig())
    centroids = attacker._find_buildings_by_color(screen)
    print(f"Found {len(centroids)} building candidates")

    # Draw results
    out = screen.copy()
    for cx, cy in centroids:
        cv2.circle(out, (cx, cy), 20, (0, 255, 0), 3)
        cv2.circle(out, (cx, cy), 3, (0, 255, 0), -1)

    # Show no-deploy zone
    no_deploy = attacker._build_no_deploy_mask(screen)
    red_overlay = out.copy()
    red_overlay[no_deploy > 0] = [0, 0, 180]
    out = cv2.addWeighted(out, 0.6, red_overlay, 0.4, 0)
    cv2.imwrite("debug_no_deploy_mask.png", no_deploy)
    print(f"  No-deploy zone built (saved debug_no_deploy_mask.png)")

    # Also show the projected deploy points
    deploy_pts = attacker._get_targeted_deploy_points(screen, w, h)
    print(f"  Deploy points ({len(deploy_pts)}):")
    for px, py in deploy_pts:
        print(f"    ({px}, {py})")
        cv2.circle(out, (px, py), 25, (0, 0, 255), 4)
        cv2.putText(out, "X", (px - 8, py + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

    # Also save individual channel masks for tuning
    import numpy as np
    hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
    h2, w2 = screen.shape[:2]
    roi_top = int(h2 * 0.12)
    roi_bottom = int(h2 * 0.80)
    roi_left = int(w2 * 0.12)
    roi_right = int(w2 * 0.88)
    hsv_roi = hsv[roi_top:roi_bottom, roi_left:roi_right]
    gold_mask = cv2.inRange(hsv_roi, np.array([23,200,190]), np.array([32,255,255]))
    elixir_mask = cv2.inRange(hsv_roi, np.array([120,60,80]), np.array([165,255,255]))
    cv2.imwrite("debug_mask_gold.png", gold_mask)
    cv2.imwrite("debug_mask_elixir.png", elixir_mask)
    cv2.imwrite("debug_color_detect.png", out)
    print(f"Saved debug_color_detect.png")
    print(f"Saved debug_mask_gold.png and debug_mask_elixir.png (white = detected)")
    print(f"  Green circles = detected buildings ({len(centroids)})")
    print(f"  Red circles   = deploy points ({len(deploy_pts)})")

    cv2.imshow("Color Detection", cv2.resize(out, (min(w, 1280), min(h, 720))))
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
