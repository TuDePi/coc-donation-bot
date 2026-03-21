import re
import subprocess
import time
import logging
import random

import cv2
import numpy as np


logger = logging.getLogger(__name__)

# CRIT-002 fix: strict regex for valid ADB device serial strings
_SERIAL_PATTERN = re.compile(r'^[a-zA-Z0-9:._\-]{1,64}$')


class ADBController:
    """Wrapper around ADB for device communication: screenshots, taps, swipes."""

    REFERENCE_WIDTH = 1920
    REFERENCE_HEIGHT = 1080

    def __init__(self, serial=None):
        # CRIT-002 fix: validate device serial against strict pattern
        if serial and not _SERIAL_PATTERN.match(serial):
            raise ValueError(f"Invalid device serial: {serial!r}")
        self.serial = serial
        self._resolution = None

    def _cmd(self, *args):
        """Build an ADB command list."""
        cmd = ["adb"]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        return cmd

    def _run(self, *args, capture=True):
        """Run an ADB command and return output."""
        cmd = self._cmd(*args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=capture,
                timeout=10,
            )
            if result.returncode != 0 and capture:
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                if stderr:
                    logger.warning("ADB stderr: %s", stderr)
            return result
        except subprocess.TimeoutExpired:
            logger.error("ADB command timed out: %s", " ".join(cmd))
            return None
        except FileNotFoundError:
            logger.error("ADB not found. Install with: brew install android-platform-tools")
            return None

    def is_connected(self):
        """Check if a device is connected."""
        result = self._run("devices")
        if result is None:
            return False
        output = result.stdout.decode("utf-8", errors="replace")
        lines = [l.strip() for l in output.strip().split("\n")[1:] if l.strip()]
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1] == "device":
                if self.serial is None or parts[0] == self.serial:
                    return True
        return False

    def get_resolution(self):
        """Get device screen resolution as (width, height)."""
        if self._resolution:
            return self._resolution
        result = self._run("shell", "wm", "size")
        if result is None:
            return (self.REFERENCE_WIDTH, self.REFERENCE_HEIGHT)
        output = result.stdout.decode("utf-8", errors="replace").strip()
        # Output: "Physical size: 1920x1080"
        for line in output.split("\n"):
            if "size" in line.lower():
                size_str = line.split(":")[-1].strip()
                w, h = size_str.split("x")
                self._resolution = (int(w), int(h))
                return self._resolution
        return (self.REFERENCE_WIDTH, self.REFERENCE_HEIGHT)

    def screenshot(self):
        """Capture a screenshot and return as numpy array (BGR)."""
        result = self._run("exec-out", "screencap", "-p")
        if result is None or result.returncode != 0:
            logger.error("Failed to capture screenshot")
            return None
        img_array = np.frombuffer(result.stdout, dtype=np.uint8)
        if img_array.size == 0:
            logger.error("Empty screenshot data")
            return None
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if image is None:
            logger.error("Failed to decode screenshot")
            return None
        return image

    def _scale_coords(self, x, y):
        """Scale coordinates from reference resolution to device resolution."""
        w, h = self.get_resolution()
        scaled_x = int(x * w / self.REFERENCE_WIDTH)
        scaled_y = int(y * h / self.REFERENCE_HEIGHT)
        return scaled_x, scaled_y

    def tap(self, x, y, scale=True):
        """Tap at coordinates. If scale=True, coordinates are in reference resolution."""
        if scale:
            x, y = self._scale_coords(x, y)
        logger.debug("Tap at (%d, %d)", x, y)
        self._run("shell", "input", "tap", str(x), str(y))

    def tap_ratio(self, rx, ry):
        """Tap at ratio-based coordinates (0.0-1.0)."""
        w, h = self.get_resolution()
        x = int(rx * w)
        y = int(ry * h)
        logger.debug("Tap ratio (%.2f, %.2f) -> (%d, %d)", rx, ry, x, y)
        self._run("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1, y1, x2, y2, duration_ms=300, scale=True):
        """Swipe from (x1,y1) to (x2,y2)."""
        if scale:
            x1, y1 = self._scale_coords(x1, y1)
            x2, y2 = self._scale_coords(x2, y2)
        logger.debug("Swipe (%d,%d) -> (%d,%d) in %dms", x1, y1, x2, y2, duration_ms)
        self._run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))

    def long_press(self, x, y, duration_ms=1000, scale=True):
        """Long press at coordinates."""
        if scale:
            x, y = self._scale_coords(x, y)
        logger.debug("Long press at (%d, %d) for %dms", x, y, duration_ms)
        self._run("shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms))

    def random_delay(self, min_s=0.1, max_s=0.3):
        """Sleep for a random duration between min and max seconds."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)

    def tap_with_delay(self, x, y, min_delay=0.1, max_delay=0.3, scale=True):
        """Tap and then wait a random delay."""
        self.tap(x, y, scale=scale)
        self.random_delay(min_delay, max_delay)
