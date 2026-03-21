"""
Capture building templates directly from the device screen.
Run while an enemy base is visible, draw rectangles around buildings.

Usage:
    python3 tools/capture_buildings.py

Controls:
    - Drag to draw a rectangle around a building
    - Press ENTER to save it (type name in terminal)
    - Press U to undo
    - Press ESC to quit
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from bot.adb_controller import ADBController

SAVE_DIR = "templates/buildings"
WIN = "Building Capture — drag, ENTER to save, U undo, ESC quit"

drawing = False
start_x = start_y = 0
current_rect = None
saved = []
base_image = None
display_image = None


def redraw():
    global display_image
    display_image = base_image.copy()
    for name, x1, y1, x2, y2 in saved:
        cv2.rectangle(display_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(display_image, name, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
    if current_rect:
        cv2.rectangle(display_image, current_rect[:2], current_rect[2:], (0, 120, 255), 2)
    cv2.imshow(WIN, display_image)


def mouse_cb(event, x, y, flags, param):
    global drawing, start_x, start_y, current_rect
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_x, start_y = x, y
        current_rect = None
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        current_rect = (min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y))
        redraw()
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        current_rect = (min(start_x, x), min(start_y, y), max(start_x, x), max(start_y, y))
        redraw()


def main():
    global base_image, display_image, current_rect

    os.makedirs(SAVE_DIR, exist_ok=True)

    print("Connecting to device...")
    adb = ADBController()
    if not adb.is_connected():
        print("ERROR: No device connected."); sys.exit(1)

    print("Taking screenshot (enemy base should be visible)...")
    screen = adb.screenshot()
    if screen is None:
        print("ERROR: Screenshot failed."); sys.exit(1)

    h, w = screen.shape[:2]
    print(f"Screen: {w}x{h}")
    print("\nDrag a box around a building, press ENTER, type a name.")
    print("Suggested names: gold_mine, elixir_collector, dark_elixir_drill,")
    print("                 gold_storage, elixir_storage, dark_elixir_storage\n")

    base_image = screen.copy()
    display_image = base_image.copy()

    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, min(w, 1280), min(h, 720))
    cv2.setMouseCallback(WIN, mouse_cb)
    redraw()

    while True:
        key = cv2.waitKey(50) & 0xFF

        if key == 27:  # ESC
            break

        elif key in (13, 32) and current_rect:  # ENTER or SPACE
            x1, y1, x2, y2 = current_rect
            if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
                print("Too small, try again.")
                continue

            name = input(f"Name this building (e.g. gold_mine): ").strip()
            if not name:
                continue

            # Check for existing files to auto-number
            existing = [f for f in os.listdir(SAVE_DIR) if f.startswith(name)]
            idx = len(existing) + 1
            filename = f"{name}_{idx}.png" if existing else f"{name}.png"
            filepath = os.path.join(SAVE_DIR, filename)

            crop = screen[y1:y2, x1:x2]
            cv2.imwrite(filepath, crop)
            saved.append((filename, x1, y1, x2, y2))
            current_rect = None
            redraw()
            print(f"  Saved: {filepath}  ({x2-x1}x{y2-y1}px)\n")

        elif key == ord('u') and saved:
            removed = saved.pop()
            fname = os.path.join(SAVE_DIR, removed[0])
            if os.path.exists(fname):
                os.remove(fname)
            current_rect = None
            redraw()
            print(f"  Undone + deleted: {removed[0]}")

    cv2.destroyAllWindows()
    print(f"\nSaved {len(saved)} templates to {SAVE_DIR}/")
    for name, *_ in saved:
        print(f"  {name}")


if __name__ == "__main__":
    main()
