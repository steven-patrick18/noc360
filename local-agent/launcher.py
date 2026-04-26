import json
import os
import re
import shlex
import subprocess
import time
import webbrowser
from copy import deepcopy
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
import pyautogui
import pyperclip
import requests


HOST = "127.0.0.1"
PORT = 5055
LOCAL_ADDRESSES = {"127.0.0.1", "::1"}
ALLOWED_ORIGINS = {
    "https://noc360.voipzap.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
CONFIG_DIR = Path(os.environ.get("NOC360_AGENT_CONFIG_DIR", r"C:\NOC360"))
CONFIG_PATH = CONFIG_DIR / "config.json"
PACKAGE_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": list(ALLOWED_ORIGINS)}})
pyautogui.PAUSE = 0.08

LAST_RESULT = {"success": None, "message": "No launch attempted yet.", "details": []}


DEFAULT_CONFIG = {
    "anti_hack": {
        "enabled": True,
        "method": "keyboard",
        "wait_seconds": 2,
        "tab_count_to_pin": 1,
        "use_ctrl_l_before_tab": False,
        "press_escape_before_fill": True,
    },
    "vos_login": {
        "enabled": True,
        "wait_seconds": 5,
        "field_sequence": ["server_ip", "username", "password", "system_tag"],
        "press_enter_after_fill": True,
        "focus_strategy": "vos_window",
        "initial_tab_count": 0,
    },
    "versions": [],
}


def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
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
def localhost_only():
    if request.remote_addr not in LOCAL_ADDRESSES:
        return jsonify({"success": False, "message": "NOC360 Launcher accepts localhost requests only."}), 403
    if request.method == "OPTIONS":
        return "", 204
    return None


def version_name_from_path(path: Path):
    for part in reversed(path.parts):
        if re.match(r"^V\d+\.\d+\.\d+\.\d+$", part, re.IGNORECASE):
            return part
    return path.stem


def unique_versions(versions):
    seen = set()
    result = []
    for version in versions:
        name = str(version.get("name") or "").strip()
        path = str(version.get("path") or "").strip()
        if not name or not path:
            continue
        key = (name.lower(), path.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "name": name,
            "path": path,
            "args_template": str(version.get("args_template") or ""),
            "login_wait_seconds": version.get("login_wait_seconds"),
            "tab_sequence": version.get("tab_sequence") or [],
            "system_tag": str(version.get("system_tag") or ""),
        })
    return result


def merged_config(config):
    merged = deepcopy(DEFAULT_CONFIG)
    if isinstance(config, dict):
        for section in ("anti_hack", "vos_login"):
            if isinstance(config.get(section), dict):
                merged[section].update(config[section])
        merged["versions"] = unique_versions(config.get("versions", []))
    return merged


def find_exes_inside(candidate: Path):
    exes = []
    try:
        for exe in candidate.rglob("*.exe"):
            lowered = str(exe).lower()
            if "bin" in lowered and "vos" in exe.name.lower():
                exes.append(exe)
    except (PermissionError, OSError):
        return []
    return exes


def scan_vos_versions():
    roots = [Path(r"C:\Program Files (x86)"), Path(r"C:\Program Files"), Path("D:\\")]
    versions = []
    for root in roots:
        if not root.exists():
            continue
        try:
            for dirpath, dirnames, _filenames in os.walk(root):
                current = Path(dirpath)
                dirnames[:] = [
                    dirname for dirname in dirnames
                    if not dirname.startswith("$") and dirname.lower() not in {"windows", "system volume information", "$recycle.bin"}
                ]
                if current.name.upper().startswith("VOS3000"):
                    for exe in find_exes_inside(current):
                        versions.append({"name": version_name_from_path(exe), "path": str(exe), "args_template": ""})
                    dirnames[:] = []
        except (PermissionError, OSError):
            continue
    return unique_versions(versions)


def load_package_sample():
    if not PACKAGE_CONFIG_PATH.exists():
        return {"versions": []}
    try:
        with PACKAGE_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"versions": []}


def ensure_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        return
    detected = scan_vos_versions()
    config = merged_config(load_package_sample())
    config["versions"] = detected or config.get("versions", [])
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)
    if detected:
        print(f"Detected {len(detected)} VOS version(s). Config saved to {CONFIG_PATH}")
    else:
        print("No VOS3000 executable was detected automatically.")
        print(f"Edit {CONFIG_PATH} and add your VOS3000.exe paths manually.")


def load_config():
    ensure_config()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (json.JSONDecodeError, OSError):
        config = {"versions": []}
    merged = merged_config(config)
    if config != merged:
        try:
            with CONFIG_PATH.open("w", encoding="utf-8") as handle:
                json.dump(merged, handle, indent=2)
        except OSError:
            pass
    return merged


def copy_to_clipboard(text):
    try:
        pyperclip.copy(text)
        return True
    except pyperclip.PyperclipException:
        pass
    try:
        subprocess.run("clip", input=text, text=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def format_template(template, payload):
    return template.format(
        server_ip=payload.get("server_ip") or "",
        username=payload.get("username") or "",
        password=payload.get("password") or "",
        anti_hack_url=payload.get("anti_hack_url") or "",
    )


def bool_payload(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def int_payload(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_payload(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def attempt_http_anti_hack(url, pin):
    if not url or not pin:
        return False, "Anti-hack URL or PIN missing"
    candidates = [
        {"pin": pin},
        {"password": pin},
        {"pwd": pin},
        {"pass": pin},
    ]
    for data in candidates:
        try:
            response = requests.post(url, data=data, timeout=4)
            if 200 <= response.status_code < 400:
                return True, "Anti-hack HTTP submit attempted"
        except requests.RequestException:
            continue
    return False, "Anti-hack HTTP submit failed"


def keyboard_anti_hack_login(url, pin, settings, payload):
    if not url:
        return False, "Anti-hack URL missing"
    webbrowser.open(url)
    time.sleep(float_payload(payload.get("anti_hack_wait_seconds"), float(settings.get("wait_seconds") or 2)))
    if not pin:
        return False, "Anti-hack PIN missing"
    if bool_payload(payload.get("anti_hack_press_escape"), settings.get("press_escape_before_fill", True)):
        pyautogui.press("esc")
        time.sleep(0.1)
    if bool_payload(payload.get("anti_hack_use_ctrl_l"), settings.get("use_ctrl_l_before_tab", False)):
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.1)
    tab_count = int_payload(payload.get("anti_hack_tab_count_to_pin"), int(settings.get("tab_count_to_pin") or 1))
    for _ in range(max(0, tab_count)):
        pyautogui.press("tab")
        time.sleep(0.08)
    pyperclip.copy(pin)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.12)
    pyautogui.press("enter")
    return True, "Anti-hack PIN submitted"


def run_anti_hack(payload, config, auto_login):
    url = str(payload.get("anti_hack_url") or "").strip()
    pin = str(payload.get("anti_hack_password") or "").strip()
    settings = config.get("anti_hack", {})
    if not url:
        return "Anti-hack skipped: URL missing"
    if not auto_login or not settings.get("enabled", True):
        webbrowser.open(url)
        if pin:
            copy_to_clipboard(pin)
        time.sleep(float(settings.get("wait_seconds") or 2))
        return "Anti-hack opened; PIN copied"
    try:
        if str(settings.get("method") or "keyboard").lower() == "http":
            ok, message = attempt_http_anti_hack(url, pin)
            if ok:
                return message
        ok, message = keyboard_anti_hack_login(url, pin, settings, payload)
        return message if ok else f"Anti-hack opened; {message}"
    except Exception as exc:
        webbrowser.open(url)
        if pin:
            copy_to_clipboard(pin)
        return f"Anti-hack auto-login failed; page opened and PIN copied ({exc})"


def activate_window_by_keywords(keywords):
    try:
        for keyword in keywords:
            for window in pyautogui.getWindowsWithTitle(keyword):
                try:
                    if window.isMinimized:
                        window.restore()
                    window.activate()
                    time.sleep(0.5)
                    return f"Activated window: {window.title}"
                except Exception:
                    continue
    except Exception:
        return None
    return None


def focus_vos_window(strategy):
    strategy = str(strategy or "none").lower()
    if strategy in {"vos_window", "auto"}:
        activated = activate_window_by_keywords(["VOS3000", "VOS", "Login"])
        if activated:
            return activated
    if strategy == "alt_tab":
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.35)
        return "Focused using Alt+Tab"
    if strategy == "auto":
        pyautogui.hotkey("alt", "tab")
        time.sleep(0.35)
        return "Fallback focus using Alt+Tab"
    return "Focus strategy skipped"


def value_for_field(field, payload, version, config):
    if field == "system_tag":
        return str(payload.get("system_tag") or version.get("system_tag") or config.get("vos_login", {}).get("system_tag") or "")
    return str(payload.get(field) or "")


def keyboard_vos_login(payload, version, config):
    settings = config.get("vos_login", {})
    if not settings.get("enabled", True):
        return "VOS auto-login disabled in config"
    wait_seconds = payload.get("login_wait_seconds") or version.get("login_wait_seconds") or settings.get("wait_seconds") or 5
    sequence = payload.get("tab_sequence") or version.get("tab_sequence") or settings.get("field_sequence") or ["server_ip", "username", "password", "system_tag"]
    time.sleep(float_payload(wait_seconds, 5))
    focus_message = focus_vos_window(payload.get("focus_strategy") or settings.get("focus_strategy"))
    initial_tabs = int_payload(payload.get("initial_tab_count"), int(settings.get("initial_tab_count") or 0))
    for _ in range(max(0, initial_tabs)):
        pyautogui.press("tab")
        time.sleep(0.08)
    for index, field in enumerate(sequence):
        value = value_for_field(field, payload, version, config)
        if value:
            pyperclip.copy(value)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.12)
        if index < len(sequence) - 1:
            pyautogui.press("tab")
            time.sleep(0.1)
    if settings.get("press_enter_after_fill", True):
        pyautogui.press("enter")
    return f"VOS login fields filled. {focus_message}"


@app.get("/health")
def health():
    config = load_config()
    return jsonify({"status": "ok", "versions": len(config.get("versions", []))})


@app.get("/versions")
def versions():
    config = load_config()
    safe_versions = [{"name": item["name"], "args_template": bool(item.get("args_template"))} for item in config.get("versions", [])]
    return jsonify({"versions": safe_versions})


@app.get("/last-result")
def last_result():
    return jsonify(LAST_RESULT)


@app.post("/launch-vos")
def launch_vos():
    global LAST_RESULT
    payload = request.get_json(silent=True) or {}
    version_name = str(payload.get("version_name") or "").strip()
    if not version_name:
        LAST_RESULT = {"success": False, "message": "version_name is required.", "details": []}
        return jsonify(LAST_RESULT), 400

    config = load_config()
    version = next((item for item in config.get("versions", []) if item["name"].lower() == version_name.lower()), None)
    if not version:
        LAST_RESULT = {"success": False, "message": f"VOS version not found in local config: {version_name}", "details": []}
        return jsonify(LAST_RESULT), 404

    app_path = Path(version["path"])
    if not app_path.exists():
        LAST_RESULT = {"success": False, "message": f"Configured VOS app path does not exist: {app_path}", "details": []}
        return jsonify(LAST_RESULT), 404

    auto_login = bool_payload(payload.get("auto_login"), True)
    steps = []
    steps.append(run_anti_hack(payload, config, auto_login))

    args_template = str(version.get("args_template") or "").strip()
    launched_with_args = False
    try:
        if args_template:
            args = shlex.split(format_template(args_template, payload), posix=False)
            subprocess.Popen([str(app_path), *args], shell=False)
            launched_with_args = True
            steps.append("VOS app launched with configured args template")
        elif hasattr(os, "startfile"):
            os.startfile(str(app_path))  # type: ignore[attr-defined]
            steps.append(f"VOS app launched: {app_path}")
        else:
            subprocess.Popen([str(app_path)], shell=False)
            steps.append(f"VOS app launched: {app_path}")
    except OSError as exc:
        LAST_RESULT = {"success": False, "message": f"Unable to launch VOS app: {exc}", "details": steps}
        return jsonify(LAST_RESULT), 500

    login_text = "\n".join([
        f"Server: {payload.get('server_ip') or ''}",
        f"Username: {payload.get('username') or ''}",
        f"Password: {payload.get('password') or ''}",
    ])
    if auto_login and not launched_with_args:
        try:
            steps.append(keyboard_vos_login(payload, version, config))
        except Exception as exc:
            steps.append(f"VOS auto-login failed; manual login details copied ({exc})")
    elif auto_login and launched_with_args:
        steps.append("VOS launched with configured command-line arguments")
    else:
        steps.append("Auto-login disabled")
    copy_to_clipboard(login_text)
    message = "VOS launched. Auto-login attempted. Login copied to clipboard." if auto_login else "VOS launched. Login copied to clipboard."
    LAST_RESULT = {"success": True, "message": message, "details": steps}
    return jsonify(LAST_RESULT)


if __name__ == "__main__":
    ensure_config()
    print("====================================")
    print("NOC360 Local VOS Launcher")
    print("====================================")
    print(f"Listening: http://{HOST}:{PORT}")
    print(f"Config:    {CONFIG_PATH}")
    print("Keep this window open while using NOC360 VOS Desktop.")
    app.run(host=HOST, port=PORT)
