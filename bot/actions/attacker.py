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
        Evaluate a base during search. Attacks immediately (no loot filtering).
        """
        self.search_count += 1

        if self.search_count > self.config.attack.max_searches:
            logger.info("Max searches reached (%d), giving up", self.config.attack.max_searches)
            self._press_end_search(screen)
            return False

        logger.info("Base #%d — Attacking!", self.search_count)
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
        margin = 0.15

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

    def _deploy_all_troops(self, screen, deploy_points, strategy):
        """Select each troop in the bar and deploy."""
        # Find troop icons in the bottom troop bar
        troop_bar_region_y = int(screen.shape[0] * 0.88)
        troop_bar_region_h = int(screen.shape[0] * 0.12)

        # Try to find known troop icons in the troop bar
        army_config = vars(self.config.training.army)
        if not army_config:
            logger.warning("No army configured in config.training.army")
            return

        for troop_name in army_config:
            template_path = f"troops/{troop_name}.png"
            match = self.vision.find_template(screen, template_path)
            if match is None:
                logger.warning("Troop '%s' not found in troop bar", troop_name)
                continue

            # Tap the troop icon to select it
            logger.info("Selecting troop: %s at (%d, %d)", troop_name, match[0], match[1])
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.1, 0.3)

            # Deploy fixed 40 of each troop
            count = 40
            deployed = 0

            if strategy == "spam_one_side":
                mid = deploy_points[len(deploy_points) // 2]
                for _ in range(count):
                    self.adb.tap(mid[0], mid[1], scale=False)
                    self.adb.random_delay(0.02, 0.05)
                    deployed += 1
            elif strategy == "spread":
                per_point = max(1, count // len(deploy_points))
                for point in deploy_points:
                    for _ in range(per_point):
                        if deployed >= count:
                            break
                        self.adb.tap(point[0], point[1], scale=False)
                        self.adb.random_delay(0.02, 0.05)
                        deployed += 1
            elif strategy == "surgical":
                key_points = [deploy_points[0], deploy_points[len(deploy_points) // 2], deploy_points[-1]]
                per_point = max(1, count // len(key_points))
                for point in key_points:
                    for _ in range(per_point):
                        if deployed >= count:
                            break
                        self.adb.tap(point[0], point[1], scale=False)
                        self.adb.random_delay(0.02, 0.05)
                    deployed += 1
                    self.adb.random_delay(0.3, 0.6)

            logger.info("Deployed %d/%d %s", deployed, count, troop_name)
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
