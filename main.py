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
    parser.add_argument("--web", action="store_true", help="Start with web dashboard")
    parser.add_argument("--port", type=int, default=5000, help="Web dashboard port (default: 5000)")
    parser.add_argument("--host", default="0.0.0.0", help="Web dashboard host (default: 0.0.0.0)")
    parser.add_argument("--test", action="store_true", help="Skip login screen for testing")
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

    if args.web:
        from web.app import init_app, run as run_web, app as flask_app
        init_app(args.config)
        if args.test:
            flask_app.config["TEST_MODE"] = True
        print(f"\n  Dashboard: http://localhost:{args.port}\n")
        run_web(host=args.host, port=args.port)
    else:
        bot = Bot(config)
        bot.run()


if __name__ == "__main__":
    main()
