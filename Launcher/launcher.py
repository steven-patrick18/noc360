import json
import os
import subprocess
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
LOCAL_ADDRESSES = {"127.0.0.1", "::1"}

app = Flask(__name__)


def load_config():
    defaults = {"vos_v1": "", "vos_v2": ""}
    if not CONFIG_PATH.exists():
        return defaults
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        return {**defaults, **config}
    except json.JSONDecodeError:
        return defaults


def add_cors_headers(response):
    origin = request.headers.get("Origin") or "*"
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.after_request
def after_request(response):
    return add_cors_headers(response)


@app.before_request
def allow_only_localhost():
    if request.remote_addr not in LOCAL_ADDRESSES:
        return jsonify({"error": "NOC360 Launcher accepts localhost requests only."}), 403
    if request.method == "OPTIONS":
        return "", 204
    return None


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/launch")
def launch():
    data = request.get_json(silent=True) or {}
    requested_path = str(data.get("path") or data.get("version") or "").strip()
    antihack_url = str(data.get("antihack_url") or data.get("anti_hack_url") or "").strip()

    config = load_config()
    if requested_path in config:
        launch_path = str(config.get(requested_path) or "").strip()
        if not launch_path:
            return jsonify({"error": f"Launcher path not configured for {requested_path}."}), 400
    else:
        launch_path = requested_path
    if not launch_path:
        return jsonify({"error": f"Launcher path not configured for {requested_path or 'selected version'}."}), 400

    if not os.path.exists(launch_path):
        return jsonify({"error": f"Launcher path not found: {launch_path}"}), 404

    if antihack_url:
        webbrowser.open(antihack_url)
        time.sleep(2)

    try:
        if hasattr(os, "startfile"):
            os.startfile(launch_path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen([launch_path], shell=False)
    except OSError as exc:
        return jsonify({"error": f"Unable to launch VOS shortcut: {exc}"}), 500

    return jsonify({"status": "launched", "path": launch_path, "antihack_opened": bool(antihack_url)})


if __name__ == "__main__":
    print("NOC360 Local Launcher Agent")
    print("Listening on http://127.0.0.1:5055")
    print(f"Config: {CONFIG_PATH}")
    app.run(host="127.0.0.1", port=5055)
