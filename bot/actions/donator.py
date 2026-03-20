import logging
import time

from bot.adb_controller import ADBController
from bot.vision import Vision

logger = logging.getLogger(__name__)


class Donator:
    """Simple donation bot: open chat -> find donate buttons -> tap them -> go home."""

    def __init__(self, adb: ADBController, vision: Vision, config):
        self.adb = adb
        self.vision = vision
        self.config = config
        self.total_donated = 0

    def donate(self, screen):
        """
        Full donation cycle:
        1. Open clan chat (fixed coordinates - always bottom-left)
        2. Scroll through chat looking for donate buttons
        3. Tap donate button -> tap first available troop
        4. Go home (Android back button)
        """
        dry_run = self.config.safety.dry_run

        # Step 1: Open clan chat via template matching
        if not self._open_chat(screen):
            logger.warning("Chat button not found on screen")
            return 0
        time.sleep(1.5)

        # Step 2: Scan for donate buttons
        donated = 0
        max_donations = self.config.donations.max_per_cycle
        max_scrolls = 5

        for scroll_num in range(max_scrolls):
            chat_screen = self.adb.screenshot()
            if chat_screen is None:
                break

            # Find donate buttons with multi-scale matching
            requests = self._find_donate_buttons(chat_screen)

            if not requests:
                logger.debug("No donate buttons found (scroll %d/%d)", scroll_num + 1, max_scrolls)
                if scroll_num < max_scrolls - 1:
                    self._scroll_chat_up(chat_screen)
                    time.sleep(1.0)
                continue

            logger.info("Found %d donate button(s)", len(requests))

            for x, y, confidence in requests:
                if donated >= max_donations:
                    break

                if dry_run:
                    logger.info("[DRY RUN] Would tap donate at (%d, %d) conf=%.2f", x, y, confidence)
                    donated += 1
                    continue

                # Tap the donate button
                logger.info("Tapping donate button at (%d, %d) conf=%.2f", x, y, confidence)
                self.adb.tap(x, y, scale=False)
                time.sleep(0.8)

                # After tapping donate, a troop selection popup appears
                # Tap the first available troop (just tap in the popup area)
                if self._donate_first_troop():
                    donated += 1
                    time.sleep(0.5)

            if donated >= max_donations:
                break

        # Step 3: Go home
        if not dry_run:
            self._go_home()

        if donated > 0:
            self.total_donated += donated
            logger.info("Donated %d time(s) this cycle (total: %d)", donated, self.total_donated)

        return donated

    def _open_chat(self, screen):
        """Find and tap the chat button using multi-scale template matching."""
        dry_run = self.config.safety.dry_run

        for scale in [1.0, 0.75, 0.5, 1.25, 1.5]:
            match = self.vision.find_template(
                screen, "ui/chat_button.png", threshold=0.6, scale=scale
            )
            if match:
                logger.info("Chat button found at (%d, %d) conf=%.2f scale=%.2f", match[0], match[1], match[2], scale)
                if dry_run:
                    logger.info("[DRY RUN] Would tap chat button")
                else:
                    self.adb.tap(match[0], match[1], scale=False)
                return True

        return False

    def _find_donate_buttons(self, screen):
        """Find donate buttons using multi-scale template matching."""
        # Try at multiple scales in case of resolution mismatch
        for scale in [1.0, 0.75, 0.5, 1.25, 1.5]:
            matches = self.vision.find_all_templates(
                screen,
                "donations/donate_button.png",
                threshold=0.65,
                min_distance=80,
                scale=scale,
            )
            if matches:
                logger.debug("Found %d matches at scale %.2f", len(matches), scale)
                return matches
        return []

    def _donate_first_troop(self):
        """After tapping donate, tap the first troop in the popup."""
        popup_screen = self.adb.screenshot()
        if popup_screen is None:
            return False

        # Try to find specific troop templates
        troops = self.config.donations.troops_to_donate
        if isinstance(troops, list):
            for troop_name in troops:
                template_path = f"donations/troop_slots/{troop_name}_slot.png"
                # Try multi-scale for troop icons too
                for scale in [1.0, 0.75, 0.5, 1.25, 1.5]:
                    match = self.vision.find_template(
                        popup_screen, template_path, threshold=0.6, scale=scale
                    )
                    if match:
                        self.adb.tap(match[0], match[1], scale=False)
                        logger.info("Donated: %s", troop_name)
                        time.sleep(0.3)
                        return True

        # Fallback: if no troop template matched, close the popup
        logger.warning("No troop template matched in donate popup, pressing back")
        self.adb._run("shell", "input", "keyevent", "KEYCODE_BACK")
        return False

    def _scroll_chat_up(self, screen):
        """Scroll up in clan chat to find older requests."""
        if self.config.safety.dry_run:
            return
        h, w = screen.shape[:2]
        # Swipe up to see older messages
        self.adb.swipe(
            w // 2, int(h * 0.3),
            w // 2, int(h * 0.6),
            duration_ms=400,
            scale=False,
        )

    def _go_home(self):
        """Close chat and return home."""
        self.adb._run("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.5)
        self.adb._run("shell", "input", "keyevent", "KEYCODE_BACK")
        time.sleep(0.5)
