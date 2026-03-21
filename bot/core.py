import base64
import logging
import random
import signal
import threading
import time

import cv2

from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.config_loader import Config
from bot.actions.collector import Collector
from bot.actions.donator import Donator
from bot.actions.attacker import Attacker
from bot.actions.navigator import Navigator
from bot.actions.strategy_recorder import StrategyRecorder
from bot.state_machine import StateMachine, GameState

logger = logging.getLogger(__name__)


class Bot:
    """Donation-only bot. Opens clan chat, donates troops, repeats."""

    def __init__(self, config: Config):
        self.config = config
        self.running = False
        self.status = "stopped"  # stopped, running, error

        serial = config.device.serial if hasattr(config.device, "serial") else None
        self.adb = ADBController(serial=serial)

        threshold = config.vision.default_threshold if hasattr(config.vision, "default_threshold") else 0.80
        overrides = vars(config.vision.overrides) if hasattr(config.vision, "overrides") and config.vision.overrides else {}
        self.vision = Vision(templates_dir="templates", default_threshold=threshold, threshold_overrides=overrides)

        self.state_machine = StateMachine(self.vision)
        self.navigator = Navigator(self.adb, self.vision, self.state_machine)
        self.donator = Donator(self.adb, self.vision, config)
        self.collector = Collector(self.adb, self.vision, config)
        self.attacker = Attacker(self.adb, self.vision, self.navigator, config)
        self.strategy_recorder = StrategyRecorder(self.adb)

        self._start_time = None
        self._adb_fail_count = 0
        self._thread = None
        self._last_screen = None
        self._lock = threading.Lock()
        self._last_relog_time = None
        self._last_collect_time = 0
        self._collect_interval = 120  # collect every 2 minutes
        self.collecting_enabled = True  # can be toggled from web UI
        self._mode = "donate"  # "donate", "collect", or "attack"
        self._attack_searching = False
        self._relog_interval = None  # set randomly each cycle
        self._coc_package = "com.supercell.clashofclans"

    def start(self, mode="donate"):
        """Start the bot in a background thread. mode: 'donate' or 'collect'"""
        if self._thread and self._thread.is_alive():
            logger.warning("Bot is already running")
            return
        self._mode = mode
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the bot gracefully."""
        logger.info("Stop requested")
        self.running = False

    def run(self):
        """Main bot loop."""
        # Only set signal handlers if running in the main thread
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

        if not self.adb.is_connected():
            logger.error("No device connected! Connect your phone via USB and enable USB debugging.")
            self.status = "error"
            return

        res = self.adb.get_resolution()
        logger.info("Device connected: %dx%d", res[0], res[1])

        if self.config.safety.dry_run:
            logger.warning("DRY RUN MODE - no taps will be sent to device")

        self.running = True
        self.status = "running"
        self._start_time = time.time()
        self._last_relog_time = time.time()
        self._relog_interval = random.randint(180, 240)  # 3-4 minutes
        donate_interval = self.config.timing.action_cooldown.donate if hasattr(self.config.timing.action_cooldown, "donate") else 30

        logger.info("Bot started in %s mode. Checking every %ds. Relog every %ds.", self._mode, donate_interval, self._relog_interval)

        try:
            while self.running:
                try:
                    if self._exceeded_runtime():
                        logger.info("Max runtime reached, stopping.")
                        break

                    # Check if it's time to relog
                    if time.time() - self._last_relog_time >= self._relog_interval:
                        self._relog()
                        continue

                    screen = self.adb.screenshot()
                    if screen is None:
                        self._adb_fail_count += 1
                        if self._adb_fail_count > 10:
                            logger.error("ADB failed too many times, stopping.")
                            self.status = "error"
                            break
                        logger.warning("Screenshot failed, retrying in 5s")
                        time.sleep(5)
                        continue
                    self._adb_fail_count = 0

                    with self._lock:
                        self._last_screen = screen

                    if self._mode == "collect":
                        # Collect-only mode
                        logger.info("Checking for ready collectors...")
                        self.collector.collect(screen)
                        self._sleep_interruptible(donate_interval)

                    elif self._mode == "attack":
                        # Attack mode — runs a full cycle (search, battle, return)
                        self._run_attack_cycle(screen)
                        continue  # skip the sleep at the end, cycle has its own timing

                    else:
                        # Donate mode (with optional collecting)
                        if self.collecting_enabled and time.time() - self._last_collect_time >= self._collect_interval:
                            logger.info("Checking for ready collectors...")
                            collected = self.collector.collect(screen)
                            self._last_collect_time = time.time()
                            if collected > 0:
                                self._sleep_interruptible(3)
                                continue

                        donated = self.donator.donate(screen)
                        if donated > 0:
                            logger.info("Waiting %ds before next donation check", donate_interval)
                        else:
                            logger.debug("No donations made, checking again in %ds", donate_interval)

                        # Wait before next cycle
                        self._sleep_interruptible(donate_interval)

                except Exception as e:
                    logger.error("Error: %s", e, exc_info=True)
                    time.sleep(5)
        except KeyboardInterrupt:
            pass

        self.running = False
        self.status = "stopped"
        elapsed = time.time() - self._start_time if self._start_time else 0
        minutes = int(elapsed // 60)
        logger.info("Bot stopped. Runtime: %dm, Total donations: %d", minutes, self.donator.total_donated)

    def get_stats(self):
        """Return current bot stats as a dict."""
        elapsed = 0
        if self._start_time and self.running:
            elapsed = time.time() - self._start_time

        dph = 0
        if elapsed > 0:
            dph = (self.donator.total_donated / elapsed) * 3600

        connected = False
        resolution = None
        try:
            connected = self.adb.is_connected()
            if connected:
                resolution = self.adb.get_resolution()
        except Exception:
            pass

        return {
            "status": self.status,
            "mode": self._mode,
            "running": self.running,
            "uptime_seconds": int(elapsed),
            "total_donated": self.donator.total_donated,
            "donations_per_hour": round(dph, 1),
            "donation_history": self.donator.donation_history[-50:],
            "total_collected": self.collector.total_collected,
            "total_attacks": self.attacker.attack_count,
            "heroes_enabled": self.attacker.use_heroes,
            "spells_enabled": self.attacker.use_spells,
            "collecting_enabled": self.collecting_enabled,
            "device_connected": connected,
            "device_resolution": resolution,
        }

    def get_screenshot_base64(self, allow_fresh=False):
        """Return last screenshot as base64 JPEG string.
        If allow_fresh=True and no cached screen exists, take a new one.
        """
        with self._lock:
            screen = self._last_screen

        if screen is None and allow_fresh:
            try:
                screen = self.adb.screenshot()
                if screen is not None:
                    with self._lock:
                        self._last_screen = screen
            except Exception:
                return None

        if screen is None:
            return None

        _, buf = cv2.imencode(".jpg", screen, [cv2.IMWRITE_JPEG_QUALITY, 60])
        return base64.b64encode(buf).decode("utf-8")

    def _run_attack_cycle(self, screen):
        """Run one full attack cycle: search, evaluate bases, battle, return home."""
        # Check max attacks safety limit
        max_attacks = self.config.safety.max_attacks if hasattr(self.config.safety, "max_attacks") else 50
        if self.attacker.attack_count >= max_attacks:
            logger.info("Max attacks reached (%d), stopping.", max_attacks)
            self.running = False
            return

        # Step 1: Start search from home
        logger.info("Starting attack #%d", self.attacker.attack_count + 1)
        if not self.attacker.start_search():
            logger.warning("Failed to start search, retrying in 10s")
            self._sleep_interruptible(10)
            return

        # Step 2: Wait for matchmaking (10 seconds)
        logger.info("Waiting 10s for matchmaking...")
        self._sleep_interruptible(10)
        if not self.running:
            return

        # Step 3: Evaluate bases — keep pressing Next until we find a good one
        found = False
        while self.running and not found:
            screen = self.adb.screenshot()
            if screen is None:
                self._sleep_interruptible(3)
                continue

            with self._lock:
                self._last_screen = screen

            # Check if next button exists (means we're on search screen)
            next_match = self.vision.find_template(screen, "attack/next_button.png")
            if next_match:
                found = self.attacker.evaluate_base(screen)
                if not found:
                    self._sleep_interruptible(2)  # wait for next base to load
            else:
                # Might have been matched already or something went wrong
                logger.warning("Next button not found, checking for return home")
                return_match = self.vision.find_template(screen, "attack/return_home_button.png")
                if return_match:
                    # Battle ended somehow
                    self.adb.tap(return_match[0], return_match[1], scale=False)
                    self._sleep_interruptible(5)
                    return
                self._sleep_interruptible(2)

        if not self.running:
            return

        # Step 4: Battle in progress — wait for it to end
        logger.info("Troops deployed! Monitoring battle...")
        while self.running:
            self._sleep_interruptible(3)
            screen = self.adb.screenshot()
            if screen is None:
                continue

            with self._lock:
                self._last_screen = screen

            # Check for return home button (battle ended)
            return_match = self.vision.find_template(screen, "attack/return_home_button.png")
            if return_match:
                logger.info("Battle ended, returning home")
                if not self.config.safety.dry_run:
                    self.adb.tap(return_match[0], return_match[1], scale=False)
                self._sleep_interruptible(5)

                # Tap through results screen
                screen = self.adb.screenshot()
                if screen is not None:
                    self.attacker.collect_results(screen)
                break

        # Step 5: Cooldown before next attack
        if self.running:
            attack_cooldown = self.config.timing.action_cooldown.attack if hasattr(self.config.timing.action_cooldown, "attack") else 10
            logger.info("Attack complete. Waiting %ds before next attack.", attack_cooldown)
            self._sleep_interruptible(attack_cooldown)

    def _relog(self):
        """Close and reopen CoC to avoid detection."""
        logger.info("Relogging to avoid ban detection...")

        # Force stop CoC
        self.adb._run("shell", "am", "force-stop", self._coc_package)
        logger.info("CoC closed. Waiting before reopening...")

        # Wait a random amount (15-30s) to look human
        wait_time = random.randint(15, 30)
        self._sleep_interruptible(wait_time)

        if not self.running:
            return

        # Reopen CoC
        self.adb._run("shell", "monkey", "-p", self._coc_package, "-c",
                       "android.intent.category.LAUNCHER", "1")
        logger.info("CoC reopening. Waiting for game to load...")

        # Wait for game to fully load (30-45s)
        load_time = random.randint(30, 45)
        self._sleep_interruptible(load_time)

        # Set next relog interval (3-4 minutes)
        self._last_relog_time = time.time()
        self._relog_interval = random.randint(180, 240)
        logger.info("Relog complete. Next relog in %ds.", self._relog_interval)

    def _sleep_interruptible(self, seconds):
        """Sleep that can be interrupted by Ctrl+C."""
        end = time.time() + seconds
        while time.time() < end and self.running:
            time.sleep(1)

    def _exceeded_runtime(self):
        max_hours = self.config.safety.max_runtime_hours
        if max_hours and self._start_time:
            return (time.time() - self._start_time) / 3600 >= max_hours
        return False

    def _signal_handler(self, sig, frame):
        logger.info("Shutdown signal received")
        self.running = False
