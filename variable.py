import time
import httpx
import sys
import winreg
import ujson as json
from pathlib import Path
from typing import Dict, Any


def get_steam_path(config: Dict[str, Any]) -> Path:
    """Get the Steam installation path."""
    try:
        if custom_path := config.get("Custom_Steam_Path"):
            return Path(custom_path)

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return Path(winreg.QueryValueEx(key, "SteamPath")[0])
    except Exception as e:
        print(f"Failed to get Steam path: {str(e)}")
        sys.exit(1)


# Hint: This is the default configuration for OneKeyV2. Only essential settings are included.
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "Debug_Mode": False,
    "Logging_Files": True,
    "Auto_Update": {
        "Enabled": True,
        "Check_Interval": 24
    },
    "Help with GitHub Personal Token": "GitHub Personal Token can be generated in GitHub Settings under Developer settings.",
    "Help with Custom Steam path": "Use \\ in path. For example: 'C:\\Program Files (x86)\\Steam'"
}


def generate_config() -> None:
    config_path = Path("./config.json")
    if config_path.exists():
        return  # Don't overwrite existing config!

    try:
        with config_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
        print("config.json generated successfully.")
    except IOError as e:
        print(f"Failed to create config file: {str(e)}")
        sys.exit(1)


def load_config() -> Dict[str, Any]:
    """Load the configuration file."""
    config_path = Path("./config.json")
    if not config_path.exists():
        generate_config()
        print("Please fill in the configuration file and restart the program. Exiting in 5 seconds...")
        time.sleep(5)
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except json.JSONDecodeError:
        print("Configuration file is corrupted. Regenerating...")
        generate_config()
        sys.exit(1)
    except Exception as e:
        print(f"Failed to load configuration: {str(e)}")
        sys.exit(1)


CONFIG = load_config()
DEBUG_MODE = CONFIG.get("Debug_Mode", False)
LOG_FILE = CONFIG.get("Logging_Files", True)
GITHUB_TOKEN = str(CONFIG.get("Github_Personal_Token", ""))
STEAM_PATH = get_steam_path(CONFIG)
IS_CN = True

# Hint: Auto-update settings allow the tool to check for updates automatically
AUTO_UPDATE = CONFIG.get("Auto_Update", {})

# Hint: GitHub headers are used for authentication with the GitHub API
HEADER = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

# Hint: REPO_LIST contains the GitHub repositories where manifests are stored
REPO_LIST = [
    "SteamAutoCracks/ManifestHub",
    "ikun0014/ManifestHub",
    "Auiowu/ManifestAutoUpdate",
    "tymolu233/ManifestAutoUpdate-fix",
]

CLIENT = httpx.AsyncClient(verify=False)