import logging
from enum import Enum, auto

from bot.vision import Vision

logger = logging.getLogger(__name__)


class GameState(Enum):
    UNKNOWN = auto()
    HOME = auto()
    BUILDER_BASE = auto()
    TRAINING = auto()
    ATTACKING_SEARCH = auto()
    ATTACKING_BATTLE = auto()
    ATTACKING_RESULTS = auto()
    CHAT = auto()
    WAR_MAP = auto()
    POPUP = auto()
    LOADING = auto()
    DISCONNECTED = auto()


# Templates used to identify each state, checked in order.
# First match wins. Popups checked first since they overlay everything.
STATE_TEMPLATES = {
    # Popups and interruptions (highest priority)
    GameState.DISCONNECTED: [
        "popups/connection_lost.png",
    ],
    GameState.POPUP: [
        "popups/rate_us.png",
        "popups/special_offer.png",
        "popups/clan_war_prep.png",
        "popups/shield_active.png",
        "popups/maintenance_break.png",
    ],
    GameState.LOADING: [
        "state/loading_indicator.png",
    ],
    # Game screens (check in order of likelihood)
    GameState.ATTACKING_BATTLE: [
        "state/battle_indicator.png",
    ],
    GameState.ATTACKING_RESULTS: [
        "state/results_indicator.png",
    ],
    GameState.ATTACKING_SEARCH: [
        "state/search_indicator.png",
    ],
    GameState.TRAINING: [
        "state/train_indicator.png",
    ],
    GameState.CHAT: [
        "state/chat_indicator.png",
    ],
    GameState.WAR_MAP: [
        "state/war_indicator.png",
    ],
    GameState.HOME: [
        "state/home_indicator.png",
    ],
}

# Popup templates mapped to their dismiss action (template for close/ok button)
POPUP_DISMISS = {
    "popups/rate_us.png": "ui/close_button.png",
    "popups/special_offer.png": "ui/close_button.png",
    "popups/clan_war_prep.png": "ui/close_button.png",
    "popups/shield_active.png": "ui/okay_button.png",
    "popups/maintenance_break.png": None,  # Cannot dismiss, must wait
}


class StateMachine:
    """Detects and tracks the current game state via template matching."""

    def __init__(self, vision: Vision):
        self.vision = vision
        self.current_state = GameState.UNKNOWN
        self.previous_state = GameState.UNKNOWN
        self._stale_count = 0
        self._last_detected_popup = None

    def detect_state(self, screen):
        """
        Detect the current game state from a screenshot.

        Checks templates in priority order (popups first).
        Updates current_state and previous_state.
        """
        for state, templates in STATE_TEMPLATES.items():
            for template_path in templates:
                match = self.vision.find_template(screen, template_path)
                if match is not None:
                    if state == GameState.POPUP:
                        self._last_detected_popup = template_path

                    if state != self.current_state:
                        self.previous_state = self.current_state
                        self.current_state = state
                        self._stale_count = 0
                        logger.info("State: %s -> %s", self.previous_state.name, state.name)
                    else:
                        self._stale_count += 1

                    return state

        # No template matched
        if self.current_state != GameState.UNKNOWN:
            self.previous_state = self.current_state
            self.current_state = GameState.UNKNOWN
            logger.warning("State: %s -> UNKNOWN (no template matched)", self.previous_state.name)
        else:
            self._stale_count += 1

        return GameState.UNKNOWN

    @property
    def last_popup(self):
        """The template path of the last detected popup."""
        return self._last_detected_popup

    @property
    def is_stale(self):
        """True if state hasn't changed for a suspiciously long time."""
        return self._stale_count > 30  # ~30 seconds at 1 fps

    def reset_stale(self):
        self._stale_count = 0
