import logging
import time

from bot.adb_controller import ADBController
from bot.vision import Vision
from bot.actions.navigator import Navigator

logger = logging.getLogger(__name__)


class Trainer:
    """Trains troops and spells according to configured army composition."""

    def __init__(self, adb: ADBController, vision: Vision, navigator: Navigator, config):
        self.adb = adb
        self.vision = vision
        self.navigator = navigator
        self.config = config

    def train(self):
        """
        Open barracks and train the configured army composition.

        Navigates to training screen, identifies troop icons,
        and taps them the required number of times.
        """
        if not self.navigator.open_training():
            logger.warning("Failed to open training screen")
            return False

        time.sleep(0.5)
        screen = self.adb.screenshot()
        if screen is None:
            return False

        army = self.config.training.army
        if isinstance(army, dict):
            troops = army
        else:
            logger.warning("Invalid army config format")
            return False

        trained_any = False

        for troop_name, count in troops.items():
            template_path = f"troops/{troop_name}.png"
            match = self.vision.find_template(screen, template_path)

            if match is None:
                logger.debug("Troop template not found: %s", troop_name)
                continue

            logger.info("Training %d x %s", count, troop_name)

            if not self.config.safety.dry_run:
                for i in range(count):
                    self.adb.tap(match[0], match[1], scale=False)
                    self.adb.random_delay(0.05, 0.15)

            trained_any = True

        # Train spells if configured
        spells = self.config.training.spells
        if isinstance(spells, dict) and spells:
            # Look for spell factory tab
            spell_tab = self.vision.find_template(screen, "ui/spell_factory_tab.png")
            if spell_tab:
                if not self.config.safety.dry_run:
                    self.adb.tap(spell_tab[0], spell_tab[1], scale=False)
                    self.adb.random_delay(0.3, 0.6)

                screen = self.adb.screenshot()
                if screen is not None:
                    for spell_name, count in spells.items():
                        template_path = f"troops/{spell_name}.png"
                        match = self.vision.find_template(screen, template_path)
                        if match:
                            logger.info("Training %d x %s spell", count, spell_name)
                            if not self.config.safety.dry_run:
                                for i in range(count):
                                    self.adb.tap(match[0], match[1], scale=False)
                                    self.adb.random_delay(0.05, 0.15)
                            trained_any = True

        # Close training screen
        self.navigator.close_current()

        if trained_any:
            logger.info("Training complete")
        else:
            logger.debug("No troops trained (templates missing or army empty)")

        return trained_any
