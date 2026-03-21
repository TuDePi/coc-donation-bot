# Changelog

## Unreleased

### Smarter Attack Deployment
- **Loot evaluation**: OCR reads gold/elixir/dark elixir values from the search screen and skips bases below `config.attack.min_loot` thresholds
- **Color-based building detection**: Finds gold mines (yellow) and elixir collectors (purple) using HSV color detection instead of template matching
- **No-deploy zone awareness**: Builds a mask of the base interior so troops are placed outside the red zone boundary
- **Targeted deploy strategy**: Walks outward from detected buildings to find valid deploy points just outside the no-deploy zone
- **Funnel deploy strategy**: Deploys along two adjacent edges (bottom + right) for a two-pronged entry
- **Deploy until depleted**: Troops deploy in waves across all points until the troop icon grays out (saturation check), instead of a hardcoded count of 40
- **Spell deployment**: Deploys configured spells (`config.training.spells`) at center deploy point with configurable delay
- **Better hero placement**: Heroes spread across adjacent deploy points instead of stacking on the same tile
- **Dashboard toggles**: Heroes and Spells can be toggled on/off from the web dashboard
- **Fixed surgical strategy bug**: Tap counter now increments correctly inside the inner loop

### Vision Improvements
- Per-template threshold overrides via `config.yaml` (`vision.overrides`)
- OCR preprocessing: image inversion for light-on-dark text, PSM 8 mode for single-word recognition

### Web Dashboard
- Live view no longer freezes — screenshot emitter uses cached frames only, never blocks on ADB
- `--test` flag skips the login screen for local development
- CoC API explorer proxy endpoint (`/api/coc/proxy`)

### Security
- Secret key generated randomly if `COC_BOT_SECRET` env var is not set (with warning)
- Config read/write restricted to project root directory
- Strategy tap coordinates validated (integer, 0-4096 range)
- SocketIO connections require authentication (unless test mode)

### Tools
- `tools/calibrate_regions.py` — draw rectangles on screenshot to calibrate OCR regions
- `tools/debug_ocr.py` — test OCR with multiple PSM modes
- `tools/debug_color_detect.py` — visualize color-based building detection
- `tools/debug_boundary.py` — debug no-deploy zone detection
- `tools/capture_buildings.py` — capture building templates from device
- `tools/find_building_scale.py` — find correct scale for building assets
- `tools/test_deploy.py` — test troop detection and saturation check

## 0.4.0 — CoC API Explorer & Security

- CoC API explorer with server-side proxy (keeps API key off the client)
- Authentication system (signup/login with hashed passwords)
- Security audit and critical vulnerability fixes

## 0.3.0 — Attack Mode & Strategy Recorder

- Attack mode: search bases, evaluate, deploy troops, return home
- Strategy recorder: record and replay tap sequences from the dashboard
- Live screenshot view in dashboard

## 0.2.0 — Web Dashboard & Automation

- Flask + SocketIO web dashboard with real-time logs and stats
- Resource collection on a 2-minute timer with dashboard toggle
- Separate Donate/Collect/Attack start buttons
- Periodic relog cycle (3-4 min) to avoid ban detection
- Background thread signal handler fix
- Suppressed noisy werkzeug/socketio polling logs

## 0.1.0 — Initial Release

- ADB-based donation bot with template matching
- Configurable via `config.yaml`
- Dry-run mode for testing without device taps
