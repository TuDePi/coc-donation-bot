import os
import logging

import yaml

from bot.utils.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "device": {
        "serial": None,
        "reference_resolution": [1920, 1080],
    },
    "timing": {
        "loop_delay": 1.0,
        "tap_delay": [0.1, 0.3],
        "action_cooldown": {
            "collect": 300,
            "train": 120,
            "donate": 180,
            "attack": 10,
        },
    },
    "vision": {
        "default_threshold": 0.80,
        "overrides": {},
    },
    "collector": {
        "enabled": True,
        "collect_treasury": False,
    },
    "training": {
        "enabled": True,
        "army": {"barbarian": 100},
        "spells": {},
    },
    "attack": {
        "enabled": True,
        "max_searches": 50,
        "min_loot": {"gold": 200000, "elixir": 200000, "dark_elixir": 0},
        "max_trophy_target": 2500,
        "deploy_strategy": "spread",
        "deploy_side": "bottom",
        "use_heroes": True,
        "hero_deploy_delay": 5,
    },
    "donations": {
        "enabled": False,
        "troops_to_donate": ["archer"],
        "max_per_cycle": 5,
    },
    "logging": {
        "level": "INFO",
        "file": "logs/bot.log",
        "console": True,
    },
    "safety": {
        "max_runtime_hours": 8,
        "max_attacks": 50,
        "pause_on_shield": True,
        "dry_run": False,
    },
}


def _deep_merge(base, override):
    """Recursively merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    """Dot-access wrapper around a nested dict."""

    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, Config(value))
            else:
                setattr(self, key, value)

    def __repr__(self):
        return f"Config({vars(self)})"

    def get(self, key, default=None):
        return getattr(self, key, default)


def load_config(path="config.yaml"):
    """Load config from YAML file, merged with defaults."""
    if os.path.exists(path):
        with open(path, "r") as f:
            user_config = yaml.safe_load(f) or {}
        logger.info("Loaded config from %s", path)
    else:
        logger.warning("Config file not found at %s, using defaults", path)
        user_config = {}

    merged = _deep_merge(DEFAULT_CONFIG, user_config)
    return Config(merged)
