# CoC Donation Bot

An automated Clash of Clans donation bot built with Python, ADB, and OpenCV for **educational purposes only**.

> ⚠️ **Disclaimer**: This project is made strictly for educational purposes to learn about computer vision, template matching, and Android automation. Using bots in Clash of Clans violates Supercell's Terms of Service and may result in a ban. Use at your own risk.

## How It Works

The bot connects to an Android device via ADB, takes screenshots, and uses OpenCV template matching to detect UI elements on screen. It then simulates taps to navigate the game and donate troops to clan chat requests.

**Core technologies:**
- **ADB (Android Debug Bridge)** — controls the Android device over USB
- **OpenCV** — image processing and template matching
- **Python** — glue logic and automation loop

## Features

- Automatically opens clan chat
- Detects donation requests
- Donates configured troops
- Graceful shutdown with Ctrl+C

## Requirements

- Python 3.8+
- Android device with USB debugging enabled
- Clash of Clans installed on the device

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Connect your device

Enable USB debugging on your Android device and connect it via USB.

```bash
adb devices
```

You should see your device listed.

### 3. Capture templates

The bot needs template images from your specific device. With CoC open, capture each template:

```bash
python3 tools/capture_template.py templates/ui/chat_button.png
python3 tools/capture_template.py templates/donations/donate_button.png
python3 tools/capture_template.py templates/donations/troop_slots/archer_slot.png
```

Draw a tight rectangle around each UI element when prompted.

### 4. Test templates

Verify your templates match correctly:

```bash
python3 tools/test_match.py templates/ui/chat_button.png 0.6
```

### 5. Run the bot

```bash
python3 main.py
```

Options:
- `--dry-run` — takes screenshots and detects elements without tapping
- `--debug` — enables verbose logging

## Running on Raspberry Pi

This bot runs on a Raspberry Pi (Pi 4 recommended):

```bash
sudo apt install adb python3-pip
pip install opencv-python-headless numpy pyyaml
python3 main.py
```

Capture templates on your main machine first, then copy the project to the Pi.

## Project Structure

```
├── main.py                  # Entry point
├── config.yaml              # Bot configuration
├── bot/
│   ├── core.py              # Main bot loop
│   ├── vision.py            # OpenCV template matching
│   ├── adb_controller.py    # ADB device communication
│   ├── state_machine.py     # Game state detection
│   └── actions/
│       └── donator.py       # Donation logic
├── templates/               # Template images (device-specific)
│   ├── ui/
│   ├── donations/
│   ├── collectors/
│   └── state/
└── tools/
    ├── capture_template.py  # Template capture tool
    └── test_match.py        # Template testing tool
```

## Educational Topics Covered

- **Computer Vision** — template matching with OpenCV (`cv2.matchTemplate`)
- **Android Automation** — controlling devices with ADB
- **State Machines** — detecting and managing game states
- **Image Processing** — screenshot capture, scaling, and comparison

## License

This project is for educational purposes only. Not affiliated with or endorsed by Supercell.
