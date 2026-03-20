# CoC Bot

An automated Clash of Clans bot built with Python, ADB, and OpenCV for **educational purposes only**.

> ⚠️ **Disclaimer**: This project is made strictly for educational purposes to learn about computer vision, template matching, and Android automation. Using bots in Clash of Clans violates Supercell's Terms of Service and may result in a ban. Use at your own risk.

## How It Works

The bot connects to an Android device via ADB, takes screenshots, and uses OpenCV template matching to detect UI elements on screen. It simulates taps to automate donations, resource collection, and attacks.

**Core technologies:**
- **ADB (Android Debug Bridge)** — controls the Android device over USB
- **OpenCV** — image processing and template matching
- **Flask + SocketIO** — web dashboard for remote control with live view
- **Python** — glue logic and automation loop

## Features

- **Donate Mode** — opens clan chat and donates troops automatically
- **Collect Mode** — taps ready resource collectors on the home screen
- **Attack Mode** — searches for bases, deploys troops, and collects results
- **Strategy Recorder** — record your attack taps and replay them
- **Web Dashboard** — control and monitor from any browser with 1 FPS live view
- **Anti-ban** — periodic relog cycle (3-4 min) to avoid detection
- Runs headless on a Raspberry Pi

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
# UI elements
python3 tools/capture_template.py templates/ui/chat_button.png
python3 tools/capture_template.py templates/ui/attack_button.png
python3 tools/capture_template.py templates/ui/home_button.png

# Donation
python3 tools/capture_template.py templates/donations/donate_button.png
python3 tools/capture_template.py templates/donations/troop_slots/archer_slot.png

# Collectors
python3 tools/capture_template.py templates/collectors/gold_mine_ready.png
python3 tools/capture_template.py templates/collectors/elixir_collector_ready.png

# Attack
python3 tools/capture_template.py templates/attack/find_match_button.png
python3 tools/capture_template.py templates/attack/confirm_attack_button.png
python3 tools/capture_template.py templates/attack/return_home_button.png

# State indicators
python3 tools/capture_template.py templates/state/home_indicator.png
python3 tools/capture_template.py templates/state/battle_indicator.png
python3 tools/capture_template.py templates/state/results_indicator.png

# Troops
python3 tools/capture_template.py templates/troops/barbarian.png
```

Draw a tight rectangle around each UI element when prompted.

### 4. Test templates

Verify your templates match correctly:

```bash
python3 tools/test_match.py templates/ui/chat_button.png 0.6
```

### 5. Run the bot

**With web dashboard (recommended):**
```bash
python3 main.py --web --port 8080
```

Then open `http://localhost:8080` in your browser and use the Donate/Collect/Attack buttons.

**Without web dashboard:**
```bash
python3 main.py
```

**Options:**
- `--web` — start with web dashboard
- `--port PORT` — web dashboard port (default: 5000)
- `--host HOST` — web dashboard host (default: 0.0.0.0)
- `--dry-run` — takes screenshots and detects elements without tapping
- `--debug` — enables verbose logging

## Web Dashboard

The web dashboard lets you control and monitor the bot from any browser on your network.

- **Live View** — 1 FPS live screenshot of the game
- **Mode Selection** — Donate, Collect, or Attack with separate buttons
- **Stats** — donations, collections, attacks tracked in real time
- **Strategy Recorder** — record and save attack strategies
- **Device Info** — connection status and resolution

Access it at `http://<device-ip>:8080` from any device on the same network.

## Running on Raspberry Pi

This bot runs headless on a Raspberry Pi (Pi 4 recommended):

```bash
sudo apt install adb python3-pip
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Tip:** If OpenCV fails to build on ARM, use `opencv-python-headless` instead.

Capture templates on your main machine first, then copy or `git clone` the project to the Pi.

```bash
python3 main.py --web --port 8080
```

Then control the bot from any browser at `http://<pi-ip>:8080`.

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
│       ├── donator.py       # Donation logic
│       ├── collector.py     # Resource collection
│       ├── attacker.py      # Attack logic & troop deployment
│       └── strategy_recorder.py  # Record & replay attacks
├── strategies/              # Saved attack strategies (JSON)
├── web/
│   ├── app.py               # Flask web dashboard
│   ├── static/              # CSS
│   └── templates/           # HTML templates
├── templates/               # Template images (device-specific)
│   ├── ui/                  # Buttons (chat, attack, home)
│   ├── donations/           # Donate button & troop slots
│   ├── collectors/          # Ready collector icons
│   ├── attack/              # Attack flow buttons
│   ├── troops/              # Troop icons for deployment
│   └── state/               # State detection indicators
└── tools/
    ├── capture_template.py  # Template capture tool
    └── test_match.py        # Template testing tool
```

## Educational Topics Covered

- **Computer Vision** — template matching with OpenCV (`cv2.matchTemplate`)
- **Android Automation** — controlling devices with ADB
- **State Machines** — detecting and managing game states
- **Image Processing** — screenshot capture, scaling, and comparison
- **Web Development** — Flask + SocketIO dashboard with live updates
- **Networking** — remote device control over LAN

## License

This project is for educational purposes only. Not affiliated with or endorsed by Supercell.
