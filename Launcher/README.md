# NOC360 Local VOS Launcher Agent

This agent runs on the operator PC and launches local VOS shortcuts for the web app.

## Setup

1. Edit `config.json` and set your local VOS shortcut paths:

```json
{
  "vos_v1": "D:\\Desktop\\SHORTCUT\\VOS3000-v1.lnk",
  "vos_v2": "D:\\Desktop\\SHORTCUT\\VOS3000-v2.lnk"
}
```

2. Install Flask:

```powershell
pip install -r Launcher\requirements.txt
```

3. Start the local agent:

```powershell
python Launcher\launcher.py
```

The agent listens only on `http://127.0.0.1:5055`.
