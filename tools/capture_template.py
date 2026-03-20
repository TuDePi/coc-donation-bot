#!/usr/bin/env python3
"""
Capture a UI element from the device screen as a template image.

Usage:
    python tools/capture_template.py [output_path]

1. Takes a screenshot from the connected device
2. Opens it in a window - draw a rectangle around the element
3. Press ENTER to save, ESC to cancel
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from bot.adb_controller import ADBController


class TemplateCapturer:
    def __init__(self):
        self.drawing = False
        self.start = None
        self.end = None
        self.image = None
        self.display = None

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start = (x, y)
            self.end = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.end = (x, y)
            self.display = self.image.copy()
            cv2.rectangle(self.display, self.start, self.end, (0, 255, 0), 2)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end = (x, y)
            self.display = self.image.copy()
            cv2.rectangle(self.display, self.start, self.end, (0, 255, 0), 2)

    def capture(self, output_path):
        adb = ADBController()
        if not adb.is_connected():
            print("ERROR: No device connected. Connect your phone via USB and enable USB debugging.")
            return False

        print("Taking screenshot...")
        self.image = adb.screenshot()
        if self.image is None:
            print("ERROR: Failed to take screenshot")
            return False

        # Keep original full-res image for cropping
        self.original = self.image.copy()
        h, w = self.image.shape[:2]

        # Scale down for display if too large
        self.scale = 1.0
        max_display = 1200
        if w > max_display:
            self.scale = max_display / w
        display_w = int(w * self.scale)
        display_h = int(h * self.scale)

        self.display = cv2.resize(self.image, (display_w, display_h))
        self.image = self.display.copy()

        window = "Draw rectangle around the element, ENTER to save, ESC to cancel"
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window, self.mouse_callback)

        print(f"Device resolution: {w}x{h}, display scale: {self.scale:.2f}")
        print("Draw a rectangle around the UI element you want to capture.")
        print("Press ENTER to save, ESC to cancel.")

        while True:
            cv2.imshow(window, self.display)
            key = cv2.waitKey(30) & 0xFF

            if key == 27:  # ESC
                print("Cancelled.")
                cv2.destroyAllWindows()
                return False
            elif key == 13:  # ENTER
                if self.start and self.end:
                    # Display coordinates
                    dx1 = min(self.start[0], self.end[0])
                    dy1 = min(self.start[1], self.end[1])
                    dx2 = max(self.start[0], self.end[0])
                    dy2 = max(self.start[1], self.end[1])

                    if dx2 - dx1 < 5 or dy2 - dy1 < 5:
                        print("Selection too small, try again.")
                        continue

                    # Scale back to original resolution for saving
                    x1 = int(dx1 / self.scale)
                    y1 = int(dy1 / self.scale)
                    x2 = int(dx2 / self.scale)
                    y2 = int(dy2 / self.scale)

                    cropped = self.original[y1:y2, x1:x2]
                    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
                    cv2.imwrite(output_path, cropped)
                    print(f"Saved template to: {output_path}")
                    print(f"Size: {x2-x1}x{y2-y1} pixels (full resolution)")
                    cv2.destroyAllWindows()
                    return True
                else:
                    print("No selection made. Draw a rectangle first.")

        cv2.destroyAllWindows()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/capture_template.py <output_path>")
        print("Example: python tools/capture_template.py templates/ui/attack_button.png")
        sys.exit(1)

    output = sys.argv[1]
    capturer = TemplateCapturer()
    success = capturer.capture(output)
    sys.exit(0 if success else 1)
