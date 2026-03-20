import logging
import signal
import time

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

        serial = config.device.serial if hasattr(config.device, "serial") else None
        self.adb = ADBController(serial=serial)

        threshold = config.vision.default_threshold if hasattr(config.vision, "default_threshold") else 0.80
        self.vision = Vision(templates_dir="templates", default_threshold=threshold)

        self.donator = Donator(self.adb, self.vision, config)

        self._start_time = None
        self._adb_fail_count = 0

    def run(self):
        """Main bot loop."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if not self.adb.is_connected():
            logger.error("No device connected! Connect your phone via USB and enable USB debugging.")
            return

        res = self.adb.get_resolution()
        logger.info("Device connected: %dx%d", res[0], res[1])

        if self.config.safety.dry_run:
            logger.warning("DRY RUN MODE - no taps will be sent to device")

        self.running = True
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
                            break
                        logger.warning("Screenshot failed, retrying in 5s")
                        time.sleep(5)
                        continue
                    self._adb_fail_count = 0

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

        elapsed = time.time() - self._start_time if self._start_time else 0
        minutes = int(elapsed // 60)
        logger.info("Bot stopped. Runtime: %dm, Total donations: %d", minutes, self.donator.total_donated)

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
