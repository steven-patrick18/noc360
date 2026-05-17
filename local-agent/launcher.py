import json
import os
import re
import shlex
import subprocess
import time
import webbrowser
from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

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
        print(f"Edit {CONFIG_PATH} and add your vos3000client.exe paths manually.")


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


class _LoginFormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_form = False
        self.captured = False
        self.action = ""
        self.method = "get"
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        attr = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form" and not self.captured:
            self.in_form = True
            self.action = attr.get("action", "")
            self.method = (attr.get("method") or "get").lower()
        elif tag == "input" and self.in_form:
            name = attr.get("name", "")
            if name:
                self.inputs.append((name, (attr.get("type") or "text").lower(), attr.get("value", "")))

    def handle_endtag(self, tag):
        if tag == "form" and self.in_form:
            self.in_form = False
            self.captured = True


def parse_login_form(html_text, page_url):
    parser = _LoginFormParser()
    try:
        parser.feed(html_text or "")
    except Exception:
        return None
    if not parser.inputs:
        return None
    action_url = urljoin(page_url, parser.action) if parser.action else page_url
    pin_field = None
    for name, itype, _value in parser.inputs:
        if itype == "password" or re.search(r"pin|pass|pwd|code|key", name, re.I):
            pin_field = name
            break
    if pin_field is None:
        for name, itype, _value in parser.inputs:
            if itype in ("text", ""):
                pin_field = name
                break
    if pin_field is None:
        return None
    # Keep hidden fields AND the submit button: PHP anti-hack handlers
    # commonly require the submit param (e.g. `if ($_POST['log'])`) to
    # actually run the whitelist, so the value must be posted too.
    data = {name: value for name, itype, value in parser.inputs if name != pin_field}
    return {"action": action_url, "method": parser.method, "pin_field": pin_field, "data": data}


def whitelist_ip(url, pin, timeout=8):
    """Whitelist this PC's IP via the VOS anti-attack page.

    Fetches the form, submits the PIN using the form's real field name,
    and verifies the response. Runs from the operator PC, so the IP that
    the VOS server whitelists is the operator's own public IP.
    """
    url = (url or "").strip()
    pin = (pin or "").strip()
    if not url:
        return False, "Anti-hack URL is not set on this VOS record"
    if not re.match(r"https?://", url, re.I):
        url = "http://" + url.lstrip("/")
    if not pin:
        return False, "Anti-hack PIN is not set on this VOS record"
    session = requests.Session()
    session.headers.update({"User-Agent": "NOC360-Launcher/1.0"})
    try:
        page = session.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return False, f"Could not reach anti-hack page: {exc}"
    form = parse_login_form(page.text, page.url)
    try:
        if form:
            payload = dict(form["data"])
            payload[form["pin_field"]] = pin
            if form["method"] == "post":
                resp = session.post(form["action"], data=payload, timeout=timeout)
            else:
                resp = session.get(form["action"], params=payload, timeout=timeout)
        else:
            resp = None
            for field in ("pin", "password", "pwd", "pass", "code"):
                try:
                    resp = session.post(url, data={field: pin}, timeout=timeout)
                    if 200 <= resp.status_code < 400:
                        break
                except requests.RequestException:
                    continue
            if resp is None:
                return False, "Anti-hack form could not be located or submitted"
    except requests.RequestException as exc:
        return False, f"Anti-hack submit failed: {exc}"
    if not (200 <= resp.status_code < 400):
        return False, f"Anti-hack server returned HTTP {resp.status_code}"
    body = (resp.text or "").lower()
    failure_markers = ("invalid", "incorrect", "wrong pin", "denied", "fail")
    success_markers = ("success", "whitelist", "added", "allowed", "成功", "已")
    if any(marker in body for marker in failure_markers):
        return False, "Anti-hack PIN rejected by the server"
    if any(marker in body for marker in success_markers):
        return True, "IP whitelisted (server confirmed)"
    if parse_login_form(resp.text, resp.url) is None:
        return True, "IP whitelist submitted (PIN accepted, form cleared)"
    return True, "IP whitelist submitted (no explicit server confirmation)"


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
    """Whitelist the operator's IP. Always runs on launch (VOS cannot
    connect until this PC's IP is whitelisted). Returns (ok, message)."""
    url = str(payload.get("anti_hack_url") or "").strip()
    pin = str(payload.get("anti_hack_password") or "").strip()
    settings = config.get("anti_hack", {})
    if not url:
        return False, "Anti-hack URL missing on this VOS record"
    if not settings.get("enabled", True):
        webbrowser.open(url)
        if pin:
            copy_to_clipboard(pin)
        return False, "Anti-hack disabled in local config; page opened and PIN copied"
    method = str(payload.get("anti_hack_method") or settings.get("method") or "http").lower()
    if method != "keyboard":
        try:
            ok, message = whitelist_ip(url, pin)
            if ok:
                return True, message
        except Exception as exc:
            message = f"HTTP whitelist error: {exc}"
        try:
            ok2, kb_message = keyboard_anti_hack_login(url, pin, settings, payload)
            return ok2, f"{message}; keyboard fallback: {kb_message}"
        except Exception as exc:
            webbrowser.open(url)
            if pin:
                copy_to_clipboard(pin)
            return False, f"{message}; keyboard fallback failed ({exc}); page opened and PIN copied"
    try:
        ok, message = keyboard_anti_hack_login(url, pin, settings, payload)
        return ok, message
    except Exception as exc:
        webbrowser.open(url)
        if pin:
            copy_to_clipboard(pin)
        return False, f"Anti-hack keyboard automation failed ({exc}); page opened and PIN copied"


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
    field_gap = max(1, int_payload(payload.get("field_gap"), int(settings.get("field_gap") or 1)))

    # Each sequence entry may be "name" or "name:tabs". The optional ":tabs"
    # is how many Tab presses are needed to REACH that field from the
    # previous one (some VOS dialogs have disabled checkboxes that change
    # the gap between specific fields). Entries with no ":tabs" use the
    # global field_gap.
    parsed = []
    for raw in sequence:
        raw = str(raw).strip()
        if not raw:
            continue
        if ":" in raw:
            name, _, gap_text = raw.partition(":")
            try:
                gap = max(0, int(gap_text))
            except ValueError:
                gap = None
        else:
            name, gap = raw, None
        parsed.append((name.strip(), gap))

    for _ in range(max(0, initial_tabs)):
        pyautogui.press("tab")
        time.sleep(0.08)

    filled = []
    submitted = False
    for index, (field, gap) in enumerate(parsed):
        if index > 0:
            tabs = gap if gap is not None else field_gap
            for _ in range(max(0, tabs)):
                pyautogui.press("tab")
                time.sleep(0.08)
            time.sleep(0.05)
        if field in ("login", "submit"):
            # Reached the Login button via Tab; activate it (Space works
            # for focused buttons; Enter as a fallback). Pressing Enter
            # while focus is in a Java text field does not reliably
            # trigger the dialog's default button, so we tab to it.
            time.sleep(0.15)
            pyautogui.press("space")
            time.sleep(0.1)
            pyautogui.press("enter")
            submitted = True
            filled.append("login")
            continue
        value = value_for_field(field, payload, version, config)
        if value:
            pyautogui.hotkey("ctrl", "a")
            pyautogui.press("backspace")
            time.sleep(0.05)
            if field in ("password", "system_tag", "uuid"):
                # Password and System ID (Uuid) boxes in VOS3000 reject
                # clipboard paste, so send them as real keystrokes instead.
                pyautogui.typewrite(value, interval=0.03)
            else:
                pyperclip.copy(value)
                pyautogui.hotkey("ctrl", "v")
            time.sleep(0.12)
            filled.append(field)
    if not submitted and settings.get("press_enter_after_fill", True):
        pyautogui.press("enter")
    names = [name for name, _ in parsed]
    skipped = [name for name in names if name not in filled]
    note = f"filled {', '.join(filled) or 'none'}"
    if skipped:
        note += f"; empty (no value on VOS record): {', '.join(skipped)}"
    return f"VOS login: {note}. {focus_message}"


def _has_java(directory):
    return (directory / "bin" / "javaw.exe").exists() or (directory / "bin" / "java.exe").exists()


def find_vos_jre(app_path):
    """Locate the JRE/JDK bundled with the VOS install. VOS3000 ships its own
    Java; the folder is usually under the version dir but its name varies
    (jre, jre1.8, java, jdk...), so accept any folder that contains java."""
    try:
        current = Path(app_path).resolve()
    except Exception:
        return None
    # Nearer roots (exe dir up to the VOS product dir) are safe to scan deeply;
    # skip a deep scan of Program Files / drive root.
    near_roots = []
    for parent in [current.parent, *current.parents][:4]:
        if parent not in near_roots and parent.exists():
            near_roots.append(parent)
    for root in near_roots:
        for name in ("jre", "jdk", "java", "."):
            candidate = (root / name) if name != "." else root
            if _has_java(candidate):
                return candidate
    for root in near_roots:
        try:
            for sub in sorted(root.iterdir()):
                if sub.is_dir() and _has_java(sub):
                    return sub
                if sub.is_dir():
                    for deeper in ("jre", "jdk", "java"):
                        if _has_java(sub / deeper):
                            return sub / deeper
        except (PermissionError, OSError):
            continue
    return None


def ensure_java_access_bridge(jre_dir):
    """Idempotently enable Java Access Bridge for the VOS JRE so its Swing
    fields become readable. Equivalent to `jabswitch -enable` but scoped to
    the VOS JRE, so the operator does not have to run anything. The JVM reads
    this at startup, so this must be called BEFORE launching VOS."""
    if not jre_dir:
        return False, "VOS JRE not found near the install path"
    props = Path(jre_dir) / "lib" / "accessibility.properties"
    try:
        existing = props.read_text(encoding="utf-8") if props.exists() else ""
        if "com.sun.java.accessibility.AccessBridge" in existing:
            return True, "Java Access Bridge already enabled"
        props.parent.mkdir(parents=True, exist_ok=True)
        body = existing.rstrip()
        body = (body + "\n" if body else "") + "assistive_technologies=com.sun.java.accessibility.AccessBridge\nscreen_magnifier_present=true\n"
        props.write_text(body, encoding="utf-8")
        return True, "Java Access Bridge enabled for VOS JRE"
    except (PermissionError, OSError) as exc:
        return False, f"Could not enable Java Access Bridge ({exc}); run jabswitch -enable as admin"


def prepare_jab_env(jre_dir):
    if not jre_dir:
        return
    bin_dir = str(Path(jre_dir) / "bin")
    os.environ["JAVA_HOME"] = str(jre_dir)
    if bin_dir.lower() not in os.environ.get("PATH", "").lower():
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


def wait_for_vos_window(timeout):
    deadline = time.time() + max(2.0, float(timeout or 5))
    while time.time() < deadline:
        try:
            for window in pyautogui.getAllWindows():
                title = window.title or ""
                if re.search(r"vos\s*\d|v\d+\.\d+\.\d+", title, re.IGNORECASE):
                    return title
        except Exception:
            pass
        time.sleep(0.5)
    return None


def jab_fill_login(window_title, payload, version, config):
    """Fill the VOS login through Java Access Bridge (language/layout
    independent). Returns (ok, message). Caller must catch exceptions and
    fall back to keyboard automation."""
    from pyjab.jabdriver import JABDriver  # optional dependency; lazy import

    settings = config.get("vos_login", {})
    sequence = payload.get("tab_sequence") or version.get("tab_sequence") or settings.get("field_sequence") or ["server_ip", "username", "password", "system_tag"]
    if isinstance(sequence, str):
        sequence = [part.strip() for part in sequence.split(",") if part.strip()]

    driver = JABDriver(window_title)

    def collect(role):
        try:
            return driver.find_elements_by_role(role) or []
        except Exception:
            return []

    def bounds_of(element):
        try:
            box = element.bounds
            return (int(box.get("y", 0)), int(box.get("x", 0)), int(box.get("width", 0)))
        except Exception:
            return (0, 0, 0)

    fields = []
    seen = set()
    for role in ("text", "password text", "combo box"):
        for element in collect(role):
            key = bounds_of(element)
            if key in seen:
                continue
            seen.add(key)
            fields.append(element)
    fields.sort(key=bounds_of)
    if not fields:
        return False, "Java Access Bridge connected but no input fields were found"

    filled = []
    for index, field in enumerate(sequence):
        if index >= len(fields):
            break
        value = value_for_field(field, payload, version, config)
        if not value:
            continue
        element = fields[index]
        try:
            element.send_text(value)
            filled.append(field)
        except Exception:
            try:
                element.text = value
                filled.append(field)
            except Exception:
                continue

    clicked = False
    for button in collect("push button"):
        try:
            name = (button.name or "").strip().lower()
        except Exception:
            name = ""
        if any(token in name for token in ("login", "log in", "登录", "ok", "connect")):
            try:
                button.click()
                clicked = True
                break
            except Exception:
                continue

    note = f"via Java Access Bridge: set {', '.join(filled) or 'none'}"
    note += "; Login clicked" if clicked else "; Login button not found - click it manually"
    return (bool(filled), note)


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

    # Prefer the central-registry path/profile sent by NOC360; fall back to local config.
    version_path = str(payload.get("version_path") or "").strip()
    local_version = next((item for item in config.get("versions", []) if item["name"].lower() == version_name.lower()), None)
    if not version_path and local_version:
        version_path = str(local_version.get("path") or "").strip()
    if not version_path:
        LAST_RESULT = {"success": False, "message": f"No install path configured for '{version_name}'. Add it in NOC360 -> VOS Launcher Versions.", "details": [], "steps": []}
        return jsonify(LAST_RESULT), 404
    app_path = Path(version_path)
    if not app_path.exists():
        LAST_RESULT = {"success": False, "message": f"VOS app not found on this PC: {app_path}", "details": [], "steps": []}
        return jsonify(LAST_RESULT), 404

    args_template = str(payload.get("args_template") or (local_version or {}).get("args_template") or "").strip()
    field_sequence = payload.get("field_sequence")
    if isinstance(field_sequence, str):
        field_sequence = [part.strip() for part in field_sequence.split(",") if part.strip()]
    version = {
        "name": version_name,
        "path": version_path,
        "args_template": args_template,
        "login_wait_seconds": payload.get("login_wait_seconds") or (local_version or {}).get("login_wait_seconds"),
        "tab_sequence": field_sequence or (local_version or {}).get("tab_sequence") or [],
        "system_tag": payload.get("system_tag") or "",
    }
    if payload.get("press_enter_after_fill") is not None:
        config.setdefault("vos_login", {})["press_enter_after_fill"] = bool_payload(payload.get("press_enter_after_fill"), True)
    if payload.get("anti_hack_wait_seconds") is not None:
        config.setdefault("anti_hack", {})["wait_seconds"] = int_payload(payload.get("anti_hack_wait_seconds"), 2)

    auto_login = bool_payload(payload.get("auto_login"), True)
    steps = []

    def add_step(key, label, ok, step_message):
        steps.append({"step": key, "label": label, "ok": bool(ok), "message": step_message})

    # Step 1 - whitelist this PC's IP (always; VOS cannot connect without it)
    wl_ok, wl_msg = run_anti_hack(payload, config, auto_login)
    add_step("whitelist", "Whitelist IP", wl_ok, wl_msg)

    # Enable Java Access Bridge BEFORE launching so the VOS JVM reads it at startup.
    jre_dir = find_vos_jre(app_path)
    jab_ready, jab_msg = ensure_java_access_bridge(jre_dir)
    if jab_ready:
        prepare_jab_env(jre_dir)

    # Step 2 - open the VOS3000 software
    launched_with_args = False
    try:
        if args_template:
            args = shlex.split(format_template(args_template, payload), posix=False)
            subprocess.Popen([str(app_path), *args], shell=False)
            launched_with_args = True
            add_step("open", "Open VOS3000", True, f"Launched with args template: {app_path}")
        elif hasattr(os, "startfile"):
            os.startfile(str(app_path))  # type: ignore[attr-defined]
            add_step("open", "Open VOS3000", True, f"Launched: {app_path}")
        else:
            subprocess.Popen([str(app_path)], shell=False)
            add_step("open", "Open VOS3000", True, f"Launched: {app_path}")
    except OSError as exc:
        add_step("open", "Open VOS3000", False, f"Unable to launch VOS app: {exc}")
        LAST_RESULT = {"success": False, "message": f"Unable to launch VOS app: {exc}", "details": [f"{s['label']}: {s['message']}" for s in steps], "steps": steps}
        return jsonify(LAST_RESULT), 500

    login_text = "\n".join([
        f"Server: {payload.get('server_ip') or ''}",
        f"Username: {payload.get('username') or ''}",
        f"Password: {payload.get('password') or ''}",
        f"System Tag: {payload.get('system_tag') or ''}",
    ])

    # Step 3 + 4 - fill credentials and submit the login
    if launched_with_args:
        add_step("credentials", "Fill credentials", True, "Sent via command-line arguments")
        add_step("login", "Log in", True, "Submitted via command-line arguments")
    elif auto_login:
        jab_done = False
        if jab_ready:
            try:
                window_title = wait_for_vos_window(payload.get("login_wait_seconds") or version.get("login_wait_seconds") or 8)
                if window_title:
                    time.sleep(1.0)
                    jab_ok, jab_note = jab_fill_login(window_title, payload, version, config)
                    if jab_ok:
                        add_step("credentials", "Fill credentials", True, jab_note)
                        add_step("login", "Log in", "clicked" in jab_note.lower(), jab_note.split(";")[-1].strip())
                        jab_done = True
            except Exception as exc:
                add_step("credentials", "Fill credentials", True, f"Java Access Bridge unavailable ({exc}); using keyboard fallback")
        if not jab_done:
            if not jab_ready:
                add_step("credentials", "Fill credentials", True, f"{jab_msg}; using keyboard fallback")
            try:
                login_message = keyboard_vos_login(payload, version, config)
                if not steps or steps[-1]["step"] != "credentials":
                    add_step("credentials", "Fill credentials", True, login_message)
                else:
                    steps[-1]["message"] += f" | {login_message}"
                press_enter = config.get("vos_login", {}).get("press_enter_after_fill", True)
                add_step("login", "Log in", True, "Login submitted" if press_enter else "Credentials filled - press Enter in VOS to log in")
            except Exception as exc:
                add_step("credentials", "Fill credentials", False, f"Auto-fill failed; login copied to clipboard ({exc})")
                add_step("login", "Log in", False, "Manual login required (details on clipboard)")
    else:
        add_step("credentials", "Fill credentials", True, "Auto-login disabled; login copied to clipboard")
        add_step("login", "Log in", True, "Manual login (details on clipboard)")

    copy_to_clipboard(login_text)
    overall_ok = all(step["ok"] for step in steps)
    if overall_ok:
        message = "VOS launched: IP whitelisted, app opened, and login completed."
    else:
        failed = ", ".join(step["label"] for step in steps if not step["ok"])
        message = f"VOS launch finished with issues ({failed}). Login copied to clipboard as fallback."
    LAST_RESULT = {"success": overall_ok, "message": message, "details": [f"{step['label']}: {step['message']}" for step in steps], "steps": steps}
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
