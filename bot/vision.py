import os
import logging

import cv2
import numpy as np

from bot.utils.regions import Region

logger = logging.getLogger(__name__)


class Vision:
    """OpenCV-based template matching and OCR for game screen analysis."""

    def __init__(self, templates_dir="templates", default_threshold=0.80):
        self.templates_dir = templates_dir
        self.default_threshold = default_threshold
        self._cache = {}  # path -> grayscale image

    def _load_template(self, path):
        """Load and cache a template image in grayscale."""
        if path in self._cache:
            return self._cache[path]

        full_path = os.path.join(self.templates_dir, path) if not os.path.isabs(path) else path
        if not os.path.exists(full_path):
            logger.warning("Template not found: %s", full_path)
            self._cache[path] = None  # cache missing so we only warn once
            return None

        img = cv2.imread(full_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.warning("Failed to read template: %s", full_path)
            self._cache[path] = None
            return None

        self._cache[path] = img
        return img

    def _to_gray(self, image):
        """Convert BGR image to grayscale if needed."""
        if len(image.shape) == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def crop_region(self, image, region):
        """Crop image to a Region."""
        h, w = image.shape[:2]
        px, py, pw, ph = region.to_pixels(w, h)
        # Clamp to image bounds
        px = max(0, min(px, w))
        py = max(0, min(py, h))
        pw = max(1, min(pw, w - px))
        ph = max(1, min(ph, h - py))
        return image[py:py + ph, px:px + pw]

    def find_template(self, screen, template_path, threshold=None, region=None, scale=1.0):
        """
        Find the best match for a template in the screen.

        Returns (x, y, confidence) in screen coordinates, or None if no match.
        x, y are the center of the matched region.
        scale: resize template by this factor before matching (useful for resolution mismatches).
        """
        threshold = threshold or self.default_threshold
        template = self._load_template(template_path)
        if template is None:
            return None

        # Apply scale to template
        if scale != 1.0:
            th, tw = template.shape[:2]
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))
            template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)

        search_area = screen
        offset_x, offset_y = 0, 0

        if region is not None:
            h, w = screen.shape[:2]
            px, py, pw, ph = region.to_pixels(w, h)
            px = max(0, min(px, w))
            py = max(0, min(py, h))
            search_area = screen[py:py + ph, px:px + pw]
            offset_x, offset_y = px, py

        gray_screen = self._to_gray(search_area)
        th, tw = template.shape[:2]

        if gray_screen.shape[0] < th or gray_screen.shape[1] < tw:
            return None

        result = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            center_x = max_loc[0] + tw // 2 + offset_x
            center_y = max_loc[1] + th // 2 + offset_y
            logger.debug("Match '%s': (%.3f) at (%d, %d) scale=%.2f", template_path, max_val, center_x, center_y, scale)
            return (center_x, center_y, max_val)

        return None

    def find_all_templates(self, screen, template_path, threshold=None, region=None, min_distance=20, scale=1.0):
        """
        Find all matches for a template above threshold.

        Returns list of (x, y, confidence) sorted by confidence descending.
        Uses non-maximum suppression to avoid duplicate detections.
        scale: resize template by this factor before matching.
        """
        threshold = threshold or self.default_threshold
        template = self._load_template(template_path)
        if template is None:
            return []

        # Apply scale to template
        if scale != 1.0:
            th, tw = template.shape[:2]
            new_w = max(1, int(tw * scale))
            new_h = max(1, int(th * scale))
            template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)

        search_area = screen
        offset_x, offset_y = 0, 0

        if region is not None:
            h, w = screen.shape[:2]
            px, py, pw, ph = region.to_pixels(w, h)
            px = max(0, min(px, w))
            py = max(0, min(py, h))
            search_area = screen[py:py + ph, px:px + pw]
            offset_x, offset_y = px, py

        gray_screen = self._to_gray(search_area)
        th, tw = template.shape[:2]

        if gray_screen.shape[0] < th or gray_screen.shape[1] < tw:
            return []

        result = cv2.matchTemplate(gray_screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        matches = []
        for pt_y, pt_x in zip(*locations):
            confidence = result[pt_y, pt_x]
            center_x = pt_x + tw // 2 + offset_x
            center_y = pt_y + th // 2 + offset_y
            matches.append((center_x, center_y, float(confidence)))

        # Non-maximum suppression
        matches.sort(key=lambda m: m[2], reverse=True)
        filtered = []
        for match in matches:
            too_close = False
            for existing in filtered:
                dist = ((match[0] - existing[0]) ** 2 + (match[1] - existing[1]) ** 2) ** 0.5
                if dist < min_distance:
                    too_close = True
                    break
            if not too_close:
                filtered.append(match)

        logger.debug("Found %d matches for '%s'", len(filtered), template_path)
        return filtered

    def find_any_template(self, screen, templates, threshold=None, region=None):
        """
        Try multiple templates, return the first match.

        templates: dict of {name: template_path} or list of template_paths
        Returns (name_or_path, x, y, confidence) or None.
        """
        if isinstance(templates, dict):
            items = templates.items()
        else:
            items = [(p, p) for p in templates]

        for name, path in items:
            match = self.find_template(screen, path, threshold=threshold, region=region)
            if match is not None:
                return (name, match[0], match[1], match[2])

        return None

    def read_number(self, screen, region):
        """
        Read a number from a screen region using pytesseract OCR.

        Returns int or None if OCR fails.
        """
        try:
            import pytesseract
        except ImportError:
            logger.warning("pytesseract not installed, cannot read numbers")
            return None

        cropped = self.crop_region(screen, region)
        gray = self._to_gray(cropped)

        # Threshold to get clean black text on white background
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Scale up for better OCR accuracy
        scale = 3
        h, w = binary.shape
        binary = cv2.resize(binary, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        text = pytesseract.image_to_string(binary, config="--psm 7 -c tessedit_char_whitelist=0123456789,.")
        text = text.strip().replace(",", "").replace(".", "").replace(" ", "")

        if text.isdigit():
            return int(text)

        logger.debug("OCR failed to read number from region, got: '%s'", text)
        return None
