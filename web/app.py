import logging
import os
import threading
import time

import yaml
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

from bot.config_loader import load_config
from bot.core import Bot

logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = "coc-bot-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

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
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    return jsonify(bot.get_stats())


@app.route("/api/start", methods=["POST"])
def api_start():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    if bot.running:
        return jsonify({"status": "already_running"})
    bot.start()
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    bot.stop()
    return jsonify({"status": "stopped"})


@app.route("/api/screenshot")
def api_screenshot():
    if bot is None:
        return jsonify({"error": "Bot not initialized"}), 500
    img = bot.get_screenshot_base64()
    if img is None:
        return jsonify({"error": "No screenshot available"}), 404
    return jsonify({"image": img})


@app.route("/api/config", methods=["GET"])
def api_config_get():
    try:
        with open(config_path, "r") as f:
            return jsonify({"config": f.read()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["POST"])
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
def api_logs():
    return jsonify({"logs": log_buffer[-100:]})


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
    """Push screenshot to all clients every 5 seconds."""
    while True:
        socketio.sleep(5)
        if bot and bot.running:
            try:
                img = bot.get_screenshot_base64()
                if img:
                    socketio.emit("screenshot", {"image": img})
            except Exception:
                pass


@socketio.on("connect")
def on_connect():
    logger.info("Web client connected")
    if bot:
        socketio.emit("stats", bot.get_stats())


def run(host="0.0.0.0", port=5000, debug=False):
    """Start the web server."""
    socketio.start_background_task(background_stats_emitter)
    socketio.start_background_task(background_screenshot_emitter)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
