import base64
import logging
import signal
import threading
import time

import cv2

from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.config_loader import Config
from bot.actions.donator import Donator

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
        self.vision = Vision(templates_dir="templates", default_threshold=threshold)

        self.donator = Donator(self.adb, self.vision, config)

        self._start_time = None
        self._adb_fail_count = 0
        self._thread = None
        self._last_screen = None
        self._lock = threading.Lock()

    def start(self):
        """Start the bot in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Bot is already running")
            return
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
        donate_interval = self.config.timing.action_cooldown.donate if hasattr(self.config.timing.action_cooldown, "donate") else 30

        logger.info("Donation bot started. Checking every %ds. Press Ctrl+C to stop.", donate_interval)

        try:
            while self.running:
                try:
                    if self._exceeded_runtime():
                        logger.info("Max runtime reached, stopping.")
                        break

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
            "running": self.running,
            "uptime_seconds": int(elapsed),
            "total_donated": self.donator.total_donated,
            "donations_per_hour": round(dph, 1),
            "donation_history": self.donator.donation_history[-50:],
            "device_connected": connected,
            "device_resolution": resolution,
        }

    def get_screenshot_base64(self):
        """Return last screenshot as base64 JPEG string."""
        with self._lock:
            screen = self._last_screen

        if screen is None:
            # Try to take a fresh one
            try:
                screen = self.adb.screenshot()
            except Exception:
                return None

        if screen is None:
            return None

        _, buf = cv2.imencode(".jpg", screen, [cv2.IMWRITE_JPEG_QUALITY, 60])
        return base64.b64encode(buf).decode("utf-8")

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
