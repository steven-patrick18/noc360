# NOC360 Local Launcher

This small local agent lets the hosted NOC360 web app launch and auto-fill the VOS3000 desktop app installed on this Windows PC.

The browser cannot directly open `C:\` or `D:\` applications from `https://noc360.voipzap.com`, so this agent runs on localhost:

```text
http://127.0.0.1:5055
```

## First Run

1. Extract the launcher ZIP.
2. Double-click `start_launcher.bat`.
3. Keep the launcher window open while using VOS Desktop from NOC360.

On first run it creates:

```text
C:\NOC360\config.json
```

It scans common locations for VOS3000 versions:

```text
C:\Program Files (x86)\
C:\Program Files\
D:\
```

If no VOS executable is detected, edit `C:\NOC360\config.json` manually.

With Auto Login enabled in NOC360, the launcher:

1. Opens the anti-hack page.
2. Pastes the anti-hack PIN and presses Enter.
3. Opens VOS3000.
4. Pastes server IP, username, password, and system tag.
5. Presses Enter.

## Config Example

```json
{
  "anti_hack": {
    "enabled": true,
    "method": "keyboard",
    "wait_seconds": 2,
    "tab_count_to_pin": 1,
    "use_ctrl_l_before_tab": false,
    "press_escape_before_fill": true
  },
  "vos_login": {
    "enabled": true,
    "wait_seconds": 5,
    "field_sequence": ["server_ip", "username", "password", "system_tag"],
    "press_enter_after_fill": true,
    "focus_strategy": "vos_window",
    "initial_tab_count": 0
  },
  "versions": [
    {
      "name": "V2.1.8.05",
      "path": "C:\\Program Files (x86)\\VOS300021805\\V2.1.8.05\\bin\\VOS3000.exe",
      "args_template": "",
      "login_wait_seconds": 5,
      "tab_sequence": ["server_ip", "username", "password", "system_tag"]
    }
  ]
}
```

`args_template` is optional. Only use it if your VOS3000 build supports command-line login. Otherwise the launcher uses local keyboard automation with `pyautogui` and clipboard paste.

If the VOS login window is not focused correctly, set:

```json
"focus_strategy": "alt_tab"
```
