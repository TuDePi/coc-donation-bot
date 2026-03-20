import logging
import time

from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.state_machine import StateMachine, GameState

logger = logging.getLogger(__name__)


class Navigator:
    """Navigate between game screens."""

    def __init__(self, adb: ADBController, vision: Vision, state_machine: StateMachine):
        self.adb = adb
        self.vision = vision
        self.sm = state_machine

    def _wait_for_state(self, target_state, timeout=10):
        """Wait until the game reaches the target state."""
        start = time.time()
        while time.time() - start < timeout:
            screen = self.adb.screenshot()
            if screen is None:
                time.sleep(1)
                continue
            state = self.sm.detect_state(screen)
            if state == target_state:
                return True
            time.sleep(0.5)
        logger.warning("Timeout waiting for state %s", target_state.name)
        return False

    def go_home(self):
        """Navigate to the home screen."""
        if self.sm.current_state == GameState.HOME:
            return True

        # Try tapping the home button
        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "ui/home_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.5, 1.0)
            return self._wait_for_state(GameState.HOME)

        # Try close button (might be in a menu)
        match = self.vision.find_template(screen, "ui/close_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.5, 1.0)
            return self._wait_for_state(GameState.HOME, timeout=5)

        # Press device back button
        self.adb._run("shell", "input", "keyevent", "KEYCODE_BACK")
        self.adb.random_delay(0.5, 1.0)
        return self._wait_for_state(GameState.HOME, timeout=5)

    def open_attack(self):
        """Open the multiplayer attack screen."""
        if self.sm.current_state != GameState.HOME:
            if not self.go_home():
                return False

        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "ui/attack_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.5, 1.0)

            # Click "Find a Match" on the attack type screen
            screen = self.adb.screenshot()
            if screen is None:
                return False
            match = self.vision.find_template(screen, "attack/find_match_button.png")
            if match:
                self.adb.tap(match[0], match[1], scale=False)
                self.adb.random_delay(1.0, 2.0)
                return self._wait_for_state(GameState.ATTACKING_SEARCH, timeout=15)

        logger.warning("Could not find attack button")
        return False

    def open_training(self):
        """Open the army training screen."""
        if self.sm.current_state != GameState.HOME:
            if not self.go_home():
                return False

        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "ui/train_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.5, 1.0)
            return self._wait_for_state(GameState.TRAINING, timeout=5)

        logger.warning("Could not find train button")
        return False

    def open_chat(self):
        """Open the clan chat."""
        if self.sm.current_state != GameState.HOME:
            if not self.go_home():
                return False

        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "ui/chat_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.5, 1.0)
            return self._wait_for_state(GameState.CHAT, timeout=5)

        logger.warning("Could not find chat button")
        return False

    def close_current(self):
        """Close whatever screen/menu is currently open."""
        screen = self.adb.screenshot()
        if screen is None:
            return False

        match = self.vision.find_template(screen, "ui/close_button.png")
        if match:
            self.adb.tap(match[0], match[1], scale=False)
            self.adb.random_delay(0.3, 0.6)
            return True

        return False

    def dismiss_popup(self, screen):
        """Try to dismiss whatever popup is on screen."""
        popup_template = self.sm.last_popup

        if popup_template and popup_template in _POPUP_DISMISS_MAP:
            dismiss_template = _POPUP_DISMISS_MAP[popup_template]
            if dismiss_template is None:
                logger.info("Cannot dismiss popup: %s (must wait)", popup_template)
                return False
            match = self.vision.find_template(screen, dismiss_template)
            if match:
                self.adb.tap(match[0], match[1], scale=False)
                self.adb.random_delay(0.3, 0.6)
                return True

        # Fallback: try close button, then okay button
        for btn in ["ui/close_button.png", "ui/okay_button.png"]:
            match = self.vision.find_template(screen, btn)
            if match:
                self.adb.tap(match[0], match[1], scale=False)
                self.adb.random_delay(0.3, 0.6)
                return True

        # Last resort: tap center of screen
        h, w = screen.shape[:2]
        self.adb.tap(w // 2, h // 2, scale=False)
        self.adb.random_delay(0.3, 0.6)
        return True


# Import from state_machine
from bot.state_machine import POPUP_DISMISS as _POPUP_DISMISS_MAP
