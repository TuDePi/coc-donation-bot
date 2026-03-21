import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

STRATEGIES_DIR = "strategies"


def _safe_strategy_name(name: str) -> str:
    """Sanitize strategy name to alphanumeric, hyphens, and underscores only."""
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(name))[:64]
    return clean or "default"


def _safe_strategy_path(name: str) -> Path:
    """Return a resolved path within STRATEGIES_DIR, raising on traversal attempts."""
    base = Path(STRATEGIES_DIR).resolve()
    safe_name = _safe_strategy_name(name)
    candidate = (base / f"{safe_name}.json").resolve()
    if not str(candidate).startswith(str(base) + os.sep):
        raise ValueError("Path traversal attempt detected in strategy name")
    return candidate


class StrategyRecorder:
    """Records and replays touch input during attacks.

    Since getevent requires root, recording works via the web UI:
    the user clicks on the live screenshot to place taps with timing.
    """

    def __init__(self, adb):
        self.adb = adb
        self._recording = False
        self._events = []
        self._start_time = None

    def start_recording(self):
        """Start recording mode — taps are added via add_tap()."""
        os.makedirs(STRATEGIES_DIR, exist_ok=True)
        self._events = []
        self._recording = True
        self._start_time = time.time()
        logger.info("Strategy recording started — tap on the live screenshot to record!")

    def add_tap(self, x, y):
        """Add a tap event at the current time offset."""
        if not self._recording:
            return
        elapsed = time.time() - self._start_time
        self._events.append({
            "type": "tap",
            "x": x,
            "y": y,
            "time": round(elapsed, 3),
        })
        logger.info("Recorded tap at (%d, %d) t=%.1fs", x, y, elapsed)

    def stop_recording(self, name="default"):
        """Stop recording and save the strategy."""
        self._recording = False

        if not self._events:
            logger.warning("No taps recorded")
            return None

        safe_name = _safe_strategy_name(name)
        filepath = str(_safe_strategy_path(name))
        strategy = {
            "name": safe_name,
            "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": round(time.time() - self._start_time, 1),
            "resolution": list(self.adb.get_resolution()),
            "events": self._events,
        }

        with open(filepath, "w") as f:
            json.dump(strategy, f, indent=2)

        logger.info("Strategy '%s' saved: %d taps, %.1fs duration",
                     safe_name, len(self._events), strategy["duration"])
        return filepath

    @property
    def is_recording(self):
        return self._recording

    def replay(self, name="default"):
        """Replay a saved strategy."""
        safe_name = _safe_strategy_name(name)
        filepath = str(_safe_strategy_path(name))
        if not os.path.exists(filepath):
            logger.error("Strategy '%s' not found at %s", safe_name, filepath)
            return False

        with open(filepath, "r") as f:
            strategy = json.load(f)

        events = strategy["events"]
        saved_res = strategy.get("resolution", [1920, 1080])
        current_res = list(self.adb.get_resolution())

        # Scale coordinates if resolution differs
        scale_x = current_res[0] / saved_res[0]
        scale_y = current_res[1] / saved_res[1]

        logger.info("Replaying strategy '%s': %d events, %.1fs duration",
                     name, len(events), strategy.get("duration", 0))

        last_time = 0
        for event in events:
            # Wait for the right timing
            delay = event["time"] - last_time
            if delay > 0:
                time.sleep(delay)
            last_time = event["time"]

            x = int(event["x"] * scale_x)
            y = int(event["y"] * scale_y)

            if event["type"] == "tap_down":
                self.adb._run("shell", "input", "tap", str(x), str(y))

        logger.info("Strategy replay complete")
        return True

    @staticmethod
    def list_strategies():
        """List all saved strategies."""
        if not os.path.exists(STRATEGIES_DIR):
            return []
        strategies = []
        for f in os.listdir(STRATEGIES_DIR):
            if f.endswith(".json"):
                filepath = os.path.join(STRATEGIES_DIR, f)
                with open(filepath, "r") as fp:
                    data = json.load(fp)
                strategies.append({
                    "name": data.get("name", f.replace(".json", "")),
                    "duration": data.get("duration", 0),
                    "events": len(data.get("events", [])),
                    "recorded_at": data.get("recorded_at", ""),
                })
        return strategies
