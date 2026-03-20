#!/usr/bin/env python3
"""Clash of Clans Donation Bot"""

import argparse

from bot.config_loader import load_config
from bot.utils.logging_setup import setup_logging
from bot.core import Bot


def main():
    parser = argparse.ArgumentParser(description="CoC Donation Bot")
    parser.add_argument("-c", "--config", default="config.yaml", help="Config file path")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without tapping")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.dry_run:
        config.safety.dry_run = True
    if args.debug:
        config.logging.level = "DEBUG"

    setup_logging(
        level=config.logging.level,
        log_file=config.logging.file,
        console=config.logging.console,
    )

    bot = Bot(config)
    bot.run()


if __name__ == "__main__":
    main()
