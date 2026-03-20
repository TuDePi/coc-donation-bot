import logging
import time

from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.actions.navigator import Navigator
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

    def start_search(self):
        """Start multiplayer matchmaking."""
        self.search_count = 0
        if not self.navigator.open_attack():
            logger.warning("Failed to open attack screen")
            return False
        logger.info("Attack search started")
        return True

    def evaluate_base(self, screen):
        """
        Evaluate a base during search. Either attack or press next.

        Reads loot values and compares against configured thresholds.
        """
        self.search_count += 1

        if self.search_count > self.config.attack.max_searches:
            logger.info("Max searches reached (%d), giving up", self.config.attack.max_searches)
            self._press_end_search(screen)
            return False

        # Read loot values via OCR
        gold = self.vision.read_number(screen, LOOT_GOLD)
        elixir = self.vision.read_number(screen, LOOT_ELIXIR)
        dark_elixir = self.vision.read_number(screen, LOOT_DARK_ELIXIR)

        logger.info(
            "Base #%d: Gold=%s, Elixir=%s, DE=%s",
            self.search_count,
            gold or "?", elixir or "?", dark_elixir or "?",
        )

        # Check against thresholds
        min_loot = self.config.attack.min_loot
        meets_criteria = True

        if gold is not None and isinstance(min_loot, dict):
            if gold < min_loot.get("gold", 0):
                meets_criteria = False
        if elixir is not None and isinstance(min_loot, dict):
            if elixir < min_loot.get("elixir", 0):
                meets_criteria = False
        if dark_elixir is not None and isinstance(min_loot, dict):
            de_min = min_loot.get("dark_elixir", 0)
            if de_min > 0 and (dark_elixir or 0) < de_min:
                meets_criteria = False

        if meets_criteria and (gold is not None or elixir is not None):
            logger.info("Base meets criteria! Deploying troops.")
            self._deploy_troops(screen)
            return True
        else:
            self._press_next(screen)
            return False

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
        """Deploy troops according to configured strategy."""
        if self.config.safety.dry_run:
            logger.info("[DRY RUN] Would deploy troops here")
            self.attack_count += 1
            return

        strategy = self.config.attack.deploy_strategy
        side = self.config.attack.deploy_side

        # Get deployment edge coordinates based on side
        h, w = screen.shape[:2]
        deploy_points = self._get_deploy_points(w, h, side)

        # Select and deploy each troop type from the troop bar
        self._deploy_all_troops(screen, deploy_points, strategy)

        # Deploy heroes after delay
        if self.config.attack.use_heroes:
            time.sleep(self.config.attack.hero_deploy_delay)
            self._deploy_heroes(deploy_points)

        self.attack_count += 1
        logger.info("Attack #%d deployed", self.attack_count)

    def _get_deploy_points(self, w, h, side):
        """Get a list of deployment coordinates along the specified edge."""
        num_points = 10
        margin = 0.05

        if side == "bottom":
            y = int(h * 0.85)
            return [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), y) for i in range(num_points)]
        elif side == "top":
            y = int(h * 0.15)
            return [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), y) for i in range(num_points)]
        elif side == "left":
            x = int(w * 0.15)
            return [(x, int(h * (margin + i * (1 - 2 * margin) / (num_points - 1)))) for i in range(num_points)]
        elif side == "right":
            x = int(w * 0.85)
            return [(x, int(h * (margin + i * (1 - 2 * margin) / (num_points - 1)))) for i in range(num_points)]
        else:
            # Default to bottom
            y = int(h * 0.85)
            return [(int(w * (margin + i * (1 - 2 * margin) / (num_points - 1))), y) for i in range(num_points)]

    def _deploy_all_troops(self, screen, deploy_points, strategy):
        """Select each troop in the bar and deploy."""
        # Find troop icons in the bottom troop bar
        troop_bar_region_y = int(screen.shape[0] * 0.88)
        troop_bar_region_h = int(screen.shape[0] * 0.12)

        # Try to find known troop icons in the troop bar
        army_config = self.config.training.army
        if not isinstance(army_config, dict):
            return

        for troop_name in army_config:
            template_path = f"troops/{troop_name}.png"
            match = self.vision.find_template(screen, template_path)
            if match is None:
                continue

            # Tap the troop icon to select it
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.1, 0.3)

            # Deploy along the edge
            if strategy == "spam_one_side":
                # All troops at one point
                mid = deploy_points[len(deploy_points) // 2]
                for _ in range(20):
                    self.adb.tap(mid[0], mid[1], scale=False)
                    self.adb.random_delay(0.02, 0.05)
            elif strategy == "spread":
                # Spread across all points
                for point in deploy_points:
                    for _ in range(3):
                        self.adb.tap(point[0], point[1], scale=False)
                        self.adb.random_delay(0.02, 0.05)
            elif strategy == "surgical":
                # Deploy at fewer, specific points
                key_points = [deploy_points[0], deploy_points[len(deploy_points) // 2], deploy_points[-1]]
                for point in key_points:
                    for _ in range(8):
                        self.adb.tap(point[0], point[1], scale=False)
                        self.adb.random_delay(0.02, 0.05)
                    self.adb.random_delay(0.3, 0.6)

            self.adb.random_delay(0.3, 0.5)

    def _deploy_heroes(self, deploy_points):
        """Deploy heroes at the center deployment point."""
        screen = self.adb.screenshot()
        if screen is None:
            return

        mid = deploy_points[len(deploy_points) // 2]

        for hero_template in ["troops/king.png", "troops/queen.png", "troops/warden.png", "troops/champion.png"]:
            match = self.vision.find_template(screen, hero_template)
            if match:
                self.adb.tap(match[0], match[1], scale=False)
                self.adb.random_delay(0.1, 0.2)
                self.adb.tap(mid[0], mid[1], scale=False)
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
