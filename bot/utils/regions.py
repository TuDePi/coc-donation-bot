from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """A rectangular screen region defined by ratios (0.0-1.0)."""
    x: float  # left edge ratio
    y: float  # top edge ratio
    w: float  # width ratio
    h: float  # height ratio

    def to_pixels(self, screen_w, screen_h):
        """Convert ratios to pixel coordinates: (x, y, w, h)."""
        return (
            int(self.x * screen_w),
            int(self.y * screen_h),
            int(self.w * screen_w),
            int(self.h * screen_h),
        )


# --- Home Screen ---
ATTACK_BUTTON = Region(0.02, 0.78, 0.15, 0.12)
TRAIN_BUTTON = Region(0.15, 0.85, 0.10, 0.10)
CHAT_BUTTON = Region(0.02, 0.55, 0.06, 0.08)
SHOP_BUTTON = Region(0.90, 0.85, 0.08, 0.10)

# --- Loot Display (during attack search) ---
LOOT_GOLD = Region(0.043, 0.138, 0.116, 0.036)
LOOT_ELIXIR = Region(0.041, 0.192, 0.118, 0.037)
LOOT_DARK_ELIXIR = Region(0.042, 0.244, 0.120, 0.045)
LOOT_TROPHIES = Region(0.58, 0.21, 0.15, 0.04)

# --- Attack Search Screen ---
NEXT_BUTTON = Region(0.80, 0.85, 0.15, 0.10)
FIND_MATCH_BUTTON = Region(0.15, 0.75, 0.20, 0.10)

# --- Battle Screen ---
TROOP_BAR = Region(0.0, 0.85, 1.0, 0.15)
END_BATTLE_BUTTON = Region(0.02, 0.02, 0.10, 0.06)

# --- Training Screen ---
BARRACKS_TAB = Region(0.10, 0.10, 0.80, 0.08)
TROOP_GRID = Region(0.05, 0.25, 0.90, 0.55)
TRAIN_CLOSE = Region(0.90, 0.05, 0.08, 0.06)

# --- General UI ---
CLOSE_BUTTON = Region(0.88, 0.05, 0.08, 0.06)
HOME_BUTTON = Region(0.10, 0.02, 0.08, 0.06)

# --- Full screen (for state detection) ---
FULL_SCREEN = Region(0.0, 0.0, 1.0, 1.0)
CENTER_SCREEN = Region(0.25, 0.25, 0.50, 0.50)
