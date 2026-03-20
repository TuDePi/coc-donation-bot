import logging

from bot.adb_controller import ADBController
from bot.vision import Vision

logger = logging.getLogger(__name__)

# Template files for ready-to-collect resource indicators
COLLECTOR_TEMPLATES = [
    "collectors/gold_mine_ready.png",
    "collectors/elixir_collector_ready.png",
    "collectors/dark_elixir_drill_ready.png",
]


class Collector:
    """Collects resources from mines, collectors, and drills."""

    def __init__(self, adb: ADBController, vision: Vision, config):
        self.adb = adb
        self.vision = vision
        self.config = config
        self.total_collected = 0

    def collect(self, screen):
        """
        Find and tap all ready resource collectors on the home screen.

        Returns the number of collectors tapped.
        """
        tapped = 0

        for template_path in COLLECTOR_TEMPLATES:
            matches = self.vision.find_all_templates(
                screen,
                template_path,
                threshold=0.75,
                min_distance=50,
            )

            for x, y, confidence in matches:
                logger.info(
                    "Collecting from %s at (%d, %d) [%.2f]",
                    template_path.split("/")[-1],
                    x, y, confidence,
                )

                if not self.config.safety.dry_run:
                    self.adb.tap(x, y, scale=False)
                    self.adb.random_delay(
                        self.config.timing.tap_delay[0],
                        self.config.timing.tap_delay[1],
                    )

                tapped += 1

        if tapped > 0:
            self.total_collected += tapped
            logger.info("Collected from %d buildings (total: %d)", tapped, self.total_collected)
        else:
            logger.debug("No ready collectors found")

        return tapped
