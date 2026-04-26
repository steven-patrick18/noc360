# NOC360 Local VOS Launcher Agent

## What It Does

NOC360 runs in the browser, often from `https://noc360.voipzap.com`. A browser cannot directly open local `C:\` or `D:\` desktop applications, and it cannot silently run downloaded EXE/BAT files. The Local Launcher Agent solves that safely by running on the operator PC at:

```text
http://127.0.0.1:5055
```

After the agent is running, the VOS Desktop page can open anti-hack, paste the anti-hack PIN, launch the installed VOS3000 desktop app, paste VOS login details, press login, and keep the login details copied to the clipboard as a safe fallback.

## One-Time Install / Run

1. In NOC360, open `VOS Desktop`.
2. Click `Download NOC360 Launcher`.
3. Extract the ZIP on the operator PC.
4. Double-click `start_launcher.bat`.
5. Keep the launcher window open while launching VOS.

## Config File

On first run, the agent creates:

```text
C:\NOC360\config.json
```

It scans:

```text
C:\Program Files (x86)\
C:\Program Files\
D:\
```

and looks for VOS3000 executable files under detected VOS folders.

## Add More VOS Versions

Edit `C:\NOC360\config.json`:

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
      "name": "V2.1.8.00",
      "path": "C:\\Program Files (x86)\\VOS300021800\\V2.1.8.00\\bin\\VOS3000.exe",
  "args_template": "",
      "login_wait_seconds": 5,
      "tab_sequence": ["server_ip", "username", "password", "system_tag"]
    },
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

`args_template` is optional. Do not add it unless your VOS3000 build supports command-line login. If it is blank, the agent opens VOS and uses local UI automation through `pyautogui`.

## Auto-Login Tuning

Anti-hack PIN behavior is controlled by:

```json
"anti_hack": {
  "enabled": true,
  "method": "keyboard",
  "wait_seconds": 2,
  "tab_count_to_pin": 1,
  "use_ctrl_l_before_tab": false,
  "press_escape_before_fill": true
}
```

VOS desktop field order is controlled by:

```json
"vos_login": {
  "enabled": true,
  "wait_seconds": 5,
  "field_sequence": ["server_ip", "username", "password", "system_tag"],
  "press_enter_after_fill": true,
  "focus_strategy": "vos_window",
  "initial_tab_count": 0
}
```

If VOS does not receive keyboard focus, try:

```json
"focus_strategy": "alt_tab"
```

## Auto-Start On Windows

Press `Win + R`, run:

```text
shell:startup
```

Create a shortcut to `start_launcher.bat` in that folder.

## Troubleshooting: Agent Offline

If NOC360 shows `Not Installed / Not Running`:

1. Make sure `start_launcher.bat` is running.
2. Open `http://127.0.0.1:5055/health` in the browser.
3. If it does not open, restart the launcher.
4. If Python is missing, install Python 3 and run `start_launcher.bat` again.

## Troubleshooting: VOS Version Missing

Open:

```text
C:\NOC360\config.json
```

Add the VOS executable path manually, save, then click `Refresh Agent` in NOC360.

## Antivirus Warning

The launcher is a local Python script that opens a known local VOS app path and copies login details to the clipboard. If antivirus blocks it, allow the extracted launcher folder or run it from a trusted location such as:

```text
C:\NOC360\
```

The launcher binds only to `127.0.0.1` and never exposes your local file paths to the NOC360 server.
