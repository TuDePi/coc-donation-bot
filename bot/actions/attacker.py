import logging
import time

from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.actions.navigator import Navigator
from bot.actions.strategy_recorder import StrategyRecorder
from bot.utils.regions import LOOT_GOLD, LOOT_ELIXIR, LOOT_DARK_ELIXIR

logger = logging.getLogger(__name__)


class Attacker:
    """Handles farming attacks: search, evaluate, deploy troops."""

    def __init__(self, adb: ADBController, vision: Vision, navigator: Navigator, config):
        self.adb = adb
        self.vision = vision
        self.navigator = navigator
        self.config = config
        self.search_count = 0
        self.attack_count = 0
        self.strategy_name = None  # set to use a recorded strategy
        self.use_heroes = False    # runtime toggle; default off
        self.use_spells = False    # runtime toggle; default off

    def start_search(self):
        """Start multiplayer matchmaking by tapping attack button then find match."""
        self.search_count = 0

        # Step 1: Find and tap the attack button on home screen
        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "ui/attack_button.png")
        if not match:
            logger.warning("Attack button not found on screen")
            return False

        self.adb.tap(match[0], match[1], scale=False)
        self.adb.random_delay(1.0, 2.0)

        # Step 2: Find and tap "Find a Match"
        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "attack/find_match_button.png")
        if not match:
            logger.warning("Find Match button not found")
            return False

        self.adb.tap(match[0], match[1], scale=False)
        self.adb.random_delay(1.0, 2.0)

        # Step 3: Confirm attack on confirmation screen
        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "attack/confirm_attack_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(1.0, 2.0)

        logger.info("Attack search started")
        return True

    def evaluate_base(self, screen):
        """
        Evaluate a base during search using OCR loot values.
        Skips bases below configured min_loot thresholds.
        """
        self.search_count += 1

        if self.search_count > self.config.attack.max_searches:
            logger.info("Max searches reached (%d), giving up", self.config.attack.max_searches)
            self._press_end_search(screen)
            return False

        # Read loot values via OCR
        gold = self.vision.read_number(screen, LOOT_GOLD) or 0
        elixir = self.vision.read_number(screen, LOOT_ELIXIR) or 0
        logger.info("Base #%d — Gold: %d, Elixir: %d", self.search_count, gold, elixir)

        min_gold = getattr(self.config.attack.min_loot, "gold", 0)
        min_elixir = getattr(self.config.attack.min_loot, "elixir", 0)
        min_dark = getattr(self.config.attack.min_loot, "dark_elixir", 0)

        if gold < min_gold or elixir < min_elixir:
            logger.info("Loot too low (gold=%d<%d or elixir=%d<%d), skipping",
                        gold, min_gold, elixir, min_elixir)
            self._press_next(screen)
            return False

        if min_dark > 0:
            dark = self.vision.read_number(screen, LOOT_DARK_ELIXIR) or 0
            logger.info("Dark elixir: %d", dark)
            if dark < min_dark:
                logger.info("Dark elixir too low (%d<%d), skipping", dark, min_dark)
                self._press_next(screen)
                return False

        logger.info("Base #%d — Loot acceptable! Attacking.", self.search_count)
        self._deploy_troops(screen)
        return True

    def _press_next(self, screen):
        """Press the Next button to skip to next base."""
        match = self.vision.find_template(screen, "attack/next_button.png")
        if match and not self.config.safety.dry_run:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.5, 1.5)

    def _press_end_search(self, screen):
        """End the search and return home."""
        match = self.vision.find_template(screen, "attack/end_battle_button.png")
        if match and not self.config.safety.dry_run:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(1.0, 2.0)
        self.navigator.go_home()

    def _deploy_troops(self, screen):
        """Deploy troops according to configured or recorded strategy."""
        if self.config.safety.dry_run:
            logger.info("[DRY RUN] Would deploy troops here")
            self.attack_count += 1
            return

        # Use recorded strategy if set
        if self.strategy_name:
            logger.info("Using recorded strategy: %s", self.strategy_name)
            recorder = StrategyRecorder(self.adb)
            if recorder.replay(self.strategy_name):
                self.attack_count += 1
                return
            logger.warning("Recorded strategy failed, falling back to default")

        strategy = self.config.attack.deploy_strategy
        side = self.config.attack.deploy_side

        # Get deployment edge coordinates based on side
        h, w = screen.shape[:2]
        if strategy == "targeted":
            deploy_points = self._get_targeted_deploy_points(screen, w, h)
            if not deploy_points:
                logger.info("No target buildings found, falling back to spread")
                deploy_points = self._get_deploy_points(w, h, side, "spread")
        else:
            deploy_points = self._get_deploy_points(w, h, side, strategy)

        # Select and deploy each troop type from the troop bar
        self._deploy_all_troops(screen, deploy_points, strategy)

        # Deploy spells after troops
        if self.use_spells:
            self._deploy_spells(deploy_points)

        # Deploy heroes after delay
        if self.use_heroes and self.config.attack.use_heroes:
            time.sleep(self.config.attack.hero_deploy_delay)
            self._deploy_heroes(deploy_points)

        self.attack_count += 1
        logger.info("Attack #%d deployed", self.attack_count)

    def _get_deploy_points(self, w, h, side, strategy=None):
        """Get a list of deployment coordinates along the specified edge(s)."""
        num_points = 10
        margin = 0.15

        if strategy == "funnel":
            # Two adjacent edges: bottom row + right column
            bottom_y = int(h * 0.70)
            bottom_pts = [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), bottom_y)
                          for i in range(num_points)]
            right_x = int(w * 0.80)
            right_pts = [(right_x, int(h * (margin + i * (1 - 2 * margin) / (num_points - 1))))
                         for i in range(num_points)]
            return bottom_pts + right_pts

        if side == "bottom":
            y = int(h * 0.70)  # above troop bar
            return [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), y) for i in range(num_points)]
        elif side == "top":
            y = int(h * 0.20)
            return [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), y) for i in range(num_points)]
        elif side == "left":
            x = int(w * 0.20)
            return [(x, int(h * (margin + i * (1 - 2 * margin) / (num_points - 1)))) for i in range(num_points)]
        elif side == "right":
            x = int(w * 0.80)
            return [(x, int(h * (margin + i * (1 - 2 * margin) / (num_points - 1)))) for i in range(num_points)]
        else:
            y = int(h * 0.70)
            return [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), y) for i in range(num_points)]

    def _find_buildings_by_color(self, screen):
        """
        Detect gold and elixir buildings by their HSV color signature.
        Returns list of (x, y) centroids for matching color blobs.
        """
        import cv2 as _cv2
        import numpy as _np

        hsv = _cv2.cvtColor(screen, _cv2.COLOR_BGR2HSV)
        h, w = screen.shape[:2]

        # Crop to base area only — exclude HUD (top), troop bar (bottom),
        # loot display (left 12%), and Next button (right 12%)
        roi_top = int(h * 0.12)
        roi_bottom = int(h * 0.80)
        roi_left = int(w * 0.12)
        roi_right = int(w * 0.88)
        hsv_roi = hsv[roi_top:roi_bottom, roi_left:roi_right]

        # Gold mines/storages — vivid yellow coins only (high saturation to exclude sandy walls)
        gold_mask = _cv2.inRange(hsv_roi,
                                  _np.array([23, 200, 190]),
                                  _np.array([32, 255, 255]))

        # Elixir collectors/storages — blue-purple to magenta
        elixir_mask = _cv2.inRange(hsv_roi,
                                    _np.array([120, 60, 80]),
                                    _np.array([165, 255, 255]))

        # Dark elixir — dark blueish/black blobs
        dark_mask = _cv2.inRange(hsv_roi,
                                  _np.array([100, 40, 15]),
                                  _np.array([140, 180, 80]))

        combined = _cv2.bitwise_or(gold_mask, _cv2.bitwise_or(elixir_mask, dark_mask))

        # Only close gaps — skip OPEN which destroys tiny blobs
        kernel = _np.ones((3, 3), _np.uint8)
        combined = _cv2.morphologyEx(combined, _cv2.MORPH_CLOSE, kernel)

        contours, _ = _cv2.findContours(combined, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)

        centroids = []
        min_area = (w * h) * 0.00003  # very small — building blobs are tiny when zoomed out
        max_area = (w * h) * 0.015    # skip large uniform regions

        for cnt in contours:
            area = _cv2.contourArea(cnt)
            if not (min_area < area < max_area):
                continue
            # Reject elongated shapes (walls, fences) using aspect ratio
            x, y, cw, ch = _cv2.boundingRect(cnt)
            aspect = max(cw, ch) / max(min(cw, ch), 1)
            if aspect > 4.0:
                continue
            M = _cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"]) + roi_left   # offset back to full screen coords
            cy = int(M["m01"] / M["m00"]) + roi_top
            centroids.append((cx, cy))

        return centroids

    def _build_no_deploy_mask(self, screen):
        """
        Build a mask of the base interior (no-deploy zone) using
        orange pixels from the boundary line + buildings, then dilating
        to fill the entire enclosed area.
        """
        import cv2 as _cv2
        import numpy as _np

        h, w = screen.shape[:2]
        hsv = _cv2.cvtColor(screen, _cv2.COLOR_BGR2HSV)

        # Catch all orange/red pixels (boundary line + building rooftops)
        mask = _cv2.inRange(hsv, _np.array([0, 100, 100]), _np.array([30, 255, 255]))

        # Black out HUD areas
        mask[:int(h * 0.08), :] = 0
        mask[int(h * 0.82):, :] = 0
        mask[:, :int(w * 0.08)] = 0
        mask[:, int(w * 0.85):] = 0
        mask[int(h * 0.75):, :int(w * 0.20)] = 0

        # Heavy dilation to fill the base interior
        kernel = _np.ones((15, 15), _np.uint8)
        mask = _cv2.dilate(mask, kernel, iterations=5)

        # Fill holes using flood fill from edges
        filled = mask.copy()
        flood_mask = _np.zeros((h + 2, w + 2), dtype=_np.uint8)
        _cv2.floodFill(filled, flood_mask, (0, 0), 255)
        # Invert: the unflooded area is the base interior
        interior = _cv2.bitwise_not(filled)
        # Combine with dilated mask
        combined = _cv2.bitwise_or(mask, interior)

        return combined

    def _get_targeted_deploy_points(self, screen, w, h):
        """
        Find resource buildings by color, then place deploy points just outside
        the deployment boundary in the direction of each building.
        """
        import numpy as _np

        map_cx = w * 0.50
        map_cy = h * 0.42
        deploy_margin_x = w * 0.06
        deploy_margin_y = h * 0.12
        troop_bar_y = h * 0.80

        buildings = self._find_buildings_by_color(screen)
        logger.info("Color detection found %d building candidates", len(buildings))
        if not buildings:
            return []

        # Build no-deploy mask (white = can't deploy here)
        no_deploy = self._build_no_deploy_mask(screen)

        deploy_points = []
        for bx, by in buildings:
            dx = bx - map_cx
            dy = by - map_cy
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist < 1:
                continue
            ndx, ndy = dx / dist, dy / dist  # unit vector away from center

            # Walk outward from building until we exit the no-deploy zone
            px, py = float(bx), float(by)
            found = False
            for step in range(1, 80):
                px = bx + ndx * step * 5
                py = by + ndy * step * 5
                ix, iy = int(px), int(py)
                # Check bounds
                if ix < 0 or ix >= w or iy < 0 or iy >= h:
                    break
                # Check if this pixel is outside the no-deploy zone
                if no_deploy[iy, ix] == 0:
                    # Add larger margin to be safely outside
                    px += ndx * 30
                    py += ndy * 30
                    found = True
                    break

            if not found:
                # Fallback: push 30px outward from building
                px = bx + ndx * 30
                py = by + ndy * 30

            # Clamp to valid deploy zone
            px = max(deploy_margin_x, min(w - deploy_margin_x, px))
            py = max(deploy_margin_y, min(troop_bar_y, py))
            deploy_points.append((int(px), int(py)))

        # Deduplicate nearby points
        filtered = []
        for pt in deploy_points:
            if not any(abs(pt[0] - e[0]) < 40 and abs(pt[1] - e[1]) < 40 for e in filtered):
                filtered.append(pt)

        logger.info("Targeted deploy points: %s", filtered)
        return filtered

    def _deploy_all_troops(self, screen, deploy_points, strategy):
        """Select each troop in the bar and deploy until troop count hits 0."""
        army_config = vars(self.config.training.army)
        if not army_config:
            logger.warning("No army configured in config.training.army")
            return

        import cv2 as _cv2
        import numpy as _np

        max_per_troop = 300  # safety cap to avoid infinite loop

        for troop_name in army_config:
            template_path = f"troops/{troop_name}.png"
            match = self.vision.find_template(screen, template_path)
            if match is None:
                logger.warning("Troop '%s' not found in troop bar", troop_name)
                continue

            # Check if troop is already depleted (grayed out icon)
            if self._is_troop_depleted(screen, match[0], match[1]):
                logger.info("Troop '%s' already at 0, skipping", troop_name)
                continue

            # Tap the troop icon to select it
            logger.info("Selecting troop: %s at (%d, %d)", troop_name, match[0], match[1])
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.1, 0.3)

            deployed = 0
            max_waves = max_per_troop // max(len(deploy_points), 1)

            for wave in range(max_waves):
                # Blast all deploy points as fast as possible
                for point in deploy_points:
                    self.adb.tap(point[0], point[1], scale=False)
                    self.adb.random_delay(0.01, 0.03)
                deployed += len(deploy_points)

                # After each wave, re-select troop and check if depleted
                self.adb.random_delay(0.2, 0.4)
                screen = self.adb.screenshot()
                if screen is None:
                    break

                # Re-select the troop first (deploying can deselect it)
                reselect = self.vision.find_template(screen, template_path)
                if reselect:
                    self.adb.tap(reselect[0], reselect[1], scale=False)
                    self.adb.random_delay(0.1, 0.2)
                    # Check if grayed out (x0)
                    if self._is_troop_depleted(screen, reselect[0], reselect[1]):
                        logger.info("Troop '%s' depleted after %d taps", troop_name, deployed)
                        break
                else:
                    # Icon truly gone from bar
                    logger.info("Troop '%s' gone from bar after %d taps", troop_name, deployed)
                    break

            logger.info("Deployed %d %s", deployed, troop_name)
            self.adb.random_delay(0.3, 0.5)

    def _is_troop_depleted(self, screen, icon_x, icon_y):
        """Check if a troop icon is grayed out (0 troops left) by measuring saturation."""
        import cv2 as _cv2
        import numpy as _np

        h, w = screen.shape[:2]
        # Crop a small region around the icon
        size = 25
        x1 = max(0, icon_x - size)
        y1 = max(0, icon_y - size)
        x2 = min(w, icon_x + size)
        y2 = min(h, icon_y + size)
        crop = screen[y1:y2, x1:x2]

        hsv = _cv2.cvtColor(crop, _cv2.COLOR_BGR2HSV)
        mean_saturation = float(_np.mean(hsv[:, :, 1]))

        # Grayed out icons have very low saturation (< 40)
        # Active icons are colorful (saturation > 60)
        depleted = mean_saturation < 40
        logger.debug("Troop at (%d,%d) saturation=%.1f depleted=%s", icon_x, icon_y, mean_saturation, depleted)
        return depleted

    def _deploy_spells(self, deploy_points):
        """Deploy configured spells at the center of the map."""
        spell_config = vars(self.config.training.spells) if hasattr(self.config.training, "spells") else {}
        if not spell_config:
            logger.debug("No spells configured, skipping spell deployment")
            return

        spell_delay = getattr(self.config.attack, "spell_deploy_delay", 1.0)
        center = deploy_points[len(deploy_points) // 2]

        screen = self.adb.screenshot()
        if screen is None:
            return

        for spell_name in spell_config:
            template_path = f"spells/{spell_name}.png"
            match = self.vision.find_template(screen, template_path)
            if match is None:
                logger.warning("Spell '%s' not found in spell bar", spell_name)
                continue

            logger.info("Deploying spell: %s", spell_name)
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.1, 0.2)
            self.adb.tap(center[0], center[1], scale=False)
            time.sleep(spell_delay)

    def _deploy_heroes(self, deploy_points):
        """Deploy heroes spread across the mid-point of the deployment line."""
        mid_idx = len(deploy_points) // 2
        offsets = [-1, 0, 1, 2]

        for i, hero_template in enumerate(["troops/king.png", "troops/queen.png",
                                           "troops/warden.png", "troops/champion.png"]):
            screen = self.adb.screenshot()
            if screen is None:
                continue

            match = self.vision.find_template(screen, hero_template)
            if match:
                idx = max(0, min(len(deploy_points) - 1, mid_idx + offsets[i]))
                point = deploy_points[idx]
                self.adb.tap(match[0], match[1], scale=False)
                self.adb.random_delay(0.1, 0.2)
                self.adb.tap(point[0], point[1], scale=False)
                self.adb.random_delay(0.3, 0.5)

    def monitor_attack(self, screen):
        """Monitor an ongoing attack. Called each loop iteration during battle."""
        # Check for end of battle (star count or return home button)
        match = self.vision.find_template(screen, "attack/return_home_button.png")
        if match:
            logger.info("Battle ended, returning home")
            if not self.config.safety.dry_run:
                self.adb.tap(match[0], match[1], scale=False)
                self.adb.random_delay(1.0, 2.0)

    def collect_results(self, screen):
        """Collect post-attack results and return home."""
        logger.info("Collecting attack results")
        # Tap anywhere to proceed through results screen
        h, w = screen.shape[:2]
        if not self.config.safety.dry_run:
            self.adb.tap(w // 2, h // 2, scale=False)
            self.adb.random_delay(1.0, 2.0)
