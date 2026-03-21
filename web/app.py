import json
import logging
import os
import threading
import time
from functools import wraps
from pathlib import Path

import yaml
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, disconnect
from werkzeug.security import generate_password_hash, check_password_hash

from bot.config_loader import load_config
from bot.core import Bot

USERS_FILE = Path("users.json")

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("COC_BOT_SECRET", "coc-bot-secret-change-me")
socketio = SocketIO(app, cors_allowed_origins="*")


# ---------- Auth helpers ----------

def load_user():
    if not USERS_FILE.exists():
        return None
    try:
        data = json.loads(USERS_FILE.read_text())
        return data if data.get("username") else None
    except Exception:
        return None


def save_user(username, password):
    USERS_FILE.write_text(json.dumps({
        "username": username,
        "password_hash": generate_password_hash(password, method="pbkdf2:sha256"),
    }))


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------- Auth routes ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    user = load_user()
    if not user:
        return redirect(url_for("signup"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == user["username"] and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Invalid username or password."
    return render_template("login.html", signup=False, error=error)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if load_user():
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or not password:
            error = "Username and password are required."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            save_user(username, password)
            return redirect(url_for("login"))
    return render_template("login.html", signup=True, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Global bot instance
bot = None
config_path = "config.yaml"
log_buffer = []
MAX_LOG_LINES = 200


class WebLogHandler(logging.Handler):
    """Captures log records and pushes them to the web UI."""

    def emit(self, record):
        msg = self.format(record)
        log_buffer.append(msg)
        if len(log_buffer) > MAX_LOG_LINES:
            log_buffer.pop(0)
        try:
            socketio.emit("log", {"message": msg})
        except Exception:
            pass


def init_app(cfg_path="config.yaml"):
    """Initialize the Flask app with config."""
    global bot, config_path
    config_path = cfg_path
    config = load_config(config_path)
    bot = Bot(config)

    # Suppress noisy werkzeug/socketio polling logs
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("engineio.server").setLevel(logging.WARNING)

    # Add web log handler
    handler = WebLogHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    ))
    logging.getLogger().addHandler(handler)

    return app


# ---------- Routes ----------

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/stats")
@login_required
def api_stats():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    return jsonify(bot.get_stats())


@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    if bot.running:
        return jsonify({"status": "already_running"})
    mode = request.json.get("mode", "donate") if request.is_json else "donate"
    bot.start(mode=mode)
    return jsonify({"status": "started", "mode": mode})


@app.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    bot.stop()
    return jsonify({"status": "stopped"})


@app.route("/api/collecting/toggle", methods=["POST"])
@login_required
def api_collecting_toggle():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    bot.collecting_enabled = not bot.collecting_enabled
    status = "enabled" if bot.collecting_enabled else "disabled"
    logger.info("Resource collecting %s", status)
    return jsonify({"collecting_enabled": bot.collecting_enabled})


@app.route("/api/screenshot")
@login_required
def api_screenshot():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    img = bot.get_screenshot_base64()
    if img is None:
        return jsonify({"error": "No screenshot available"}), 404
    return jsonify({"image": img})


@app.route("/api/config", methods=["GET"])
@login_required
def api_config_get():
    try:
        with open(config_path, "r") as f:
            return jsonify({"config": f.read()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["POST"])
@login_required
def api_config_save():
    global bot
    try:
        new_config_text = request.json.get("config", "")
        # Validate YAML
        yaml.safe_load(new_config_text)
        with open(config_path, "w") as f:
            f.write(new_config_text)

        # Reload config into bot if not running
        if not bot.running:
            config = load_config(config_path)
            bot = Bot(config)

        return jsonify({"status": "saved"})
    except yaml.YAMLError as e:
        return jsonify({"error": f"Invalid YAML: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logs")
@login_required
def api_logs():
    return jsonify({"logs": log_buffer[-100:]})


@app.route("/api/strategy/record/start", methods=["POST"])
@login_required
def api_strategy_record_start():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    bot.strategy_recorder.start_recording()
    return jsonify({"status": "recording"})


@app.route("/api/strategy/record/stop", methods=["POST"])
@login_required
def api_strategy_record_stop():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    name = request.json.get("name", "default") if request.is_json else "default"
    filepath = bot.strategy_recorder.stop_recording(name)
    if filepath:
        return jsonify({"status": "saved", "name": name, "path": filepath})
    return jsonify({"error": "No events recorded"}), 400


@app.route("/api/strategy/list")
@login_required
def api_strategy_list():
    from bot.actions.strategy_recorder import StrategyRecorder
    return jsonify({"strategies": StrategyRecorder.list_strategies()})


@app.route("/api/strategy/tap", methods=["POST"])
@login_required
def api_strategy_tap():
    """Record a tap during strategy recording, and also send it to the device."""
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    if not bot.strategy_recorder.is_recording:
        return jsonify({"error": "Not recording"}), 400
    x = request.json.get("x", 0)
    y = request.json.get("y", 0)
    bot.strategy_recorder.add_tap(x, y)
    # Also send the tap to the device so you can see it happen
    bot.adb.tap(x, y, scale=False)
    return jsonify({"status": "tapped", "x": x, "y": y})


@app.route("/api/strategy/active", methods=["POST"])
@login_required
def api_strategy_active():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    name = request.json.get("name", "") if request.is_json else ""
    bot.attacker.strategy_name = name if name else None
    logger.info("Active attack strategy: %s", name or "default")
    return jsonify({"status": "set", "name": name})


@app.route("/api/strategy/replay", methods=["POST"])
@login_required
def api_strategy_replay():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    name = request.json.get("name", "default") if request.is_json else "default"
    success = bot.strategy_recorder.replay(name)
    return jsonify({"status": "replayed" if success else "failed"})


# ---------- SocketIO background tasks ----------

def background_stats_emitter():
    """Push stats to all clients every 2 seconds."""
    while True:
        socketio.sleep(2)
        if bot:
            try:
                socketio.emit("stats", bot.get_stats())
            except Exception:
                pass


def background_screenshot_emitter():
    """Push screenshot to all clients every second."""
    while True:
        socketio.sleep(1)
        if bot and bot.running:
            try:
                img = bot.get_screenshot_base64()
                if img:
                    socketio.emit("screenshot", {"image": img})
            except Exception:
                pass


@socketio.on("connect")
def on_connect():
    if not session.get("logged_in"):
        disconnect()
        return
    logger.info("Web client connected")
    if bot:
        socketio.emit("stats", bot.get_stats())


def run(host="0.0.0.0", port=5000, debug=False):
    """Start the web server."""
    socketio.start_background_task(background_stats_emitter)
    socketio.start_background_task(background_screenshot_emitter)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
