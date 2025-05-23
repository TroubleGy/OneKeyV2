import time
import httpx
import sys
import winreg
import ujson as json
from pathlib import Path
from typing import Dict, Any
import logging

# Configure a logger for this module
LOG = logging.getLogger("OnekeyV2.Variable")

def format_stack_trace(exception: Exception) -> str:
    """Format the stack trace of an exception, returning only the error message."""
    # Remove extra information from error messages (Moved from CustomFormatter)
    if isinstance(exception, Exception): # Check if it's an exception object
         # You might want more sophisticated formatting here if needed
         return str(exception)
    return str(exception) # Handle non-exception inputs gracefully

def get_steam_path(config: Dict[str, Any]) -> Path | None:
    """Get the Steam installation path."""
    custom_path = config.get("Custom_Steam_Path")
    LOG.info(f"Attempting to get Steam path. Custom path from config: '{custom_path}'")
    try:
        if custom_path:
            path_obj = Path(custom_path)
            LOG.info(f"Checking custom path existence: {path_obj.exists()}")
            LOG.info(f"Checking custom path is directory: {path_obj.is_dir()}")
            if path_obj.exists() and path_obj.is_dir():
                LOG.info(f"Using valid custom Steam path: {path_obj}")
                return path_obj
            else:
                LOG.warning(f"Custom Steam path does not exist or is not a directory: {custom_path}")
                # Fallback to registry if custom path is invalid

        LOG.info("Attempting to get Steam path from registry.")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            reg_path = winreg.QueryValueEx(key, "SteamPath")[0]
            steam_path_from_reg = Path(reg_path)
            LOG.info(f"Steam path found in registry: {steam_path_from_reg}")
            # Also check registry path existence and if it's a directory
            LOG.info(f"Checking registry path existence: {steam_path_from_reg.exists()}")
            LOG.info(f"Checking registry path is directory: {steam_path_from_reg.is_dir()}")
            if steam_path_from_reg.exists() and steam_path_from_reg.is_dir():
                 LOG.info("Using valid Steam path from registry.")
                 return steam_path_from_reg
            else:
                 LOG.warning("Steam path from registry does not exist or is not a directory.")
                 return None # Return None if registry path is invalid

    except FileNotFoundError:
        LOG.warning("Steam registry key not found. Please ensure Steam is installed correctly or specify Custom_Steam_Path in config.")
        return None
    except Exception as e:
        LOG.error(f"Failed to get Steam path from registry: {format_stack_trace(e)}")
        return None


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


def generate_default_config_file() -> None:
    config_path = Path("./config.json")
    if config_path.exists():
        return  # Don't overwrite existing config!

    try:
        with config_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
        print("Default config.json generated successfully.")
    except IOError as e:
        print(f"Failed to create default config file: {str(e)}")


def load_config() -> Dict[str, Any] | None:
    """Load the configuration file. Returns None if file is missing or corrupted."""
    config_path = Path("./config.json")
    if not config_path.exists():
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.loads(f.read())
            if "Github_Personal_Token" not in config_data or "Custom_Steam_Path" not in config_data:
                print("Config file is missing required keys. Regenerating default.")
                generate_default_config_file()
                return None
            return config_data
    except json.JSONDecodeError:
        print("Configuration file is corrupted. Regenerating default.")
        generate_default_config_file()
        return None
    except Exception as e:
        print(f"Failed to load configuration: {str(e)}")
        return None


# Load config at startup (will return None if missing/corrupted)
# CONFIG = load_config() # Removed initial load here

# These variables will be set after successful configuration or exit (Removed initial None assignment)
# DEBUG_MODE = False
# LOG_FILE = False
# GITHUB_TOKEN = ""
# STEAM_PATH = None # STEAM_PATH will be Path object or None
# IS_CN = True # Keep initial IS_CN = True

# AUTO_UPDATE = {} # Removed initial empty dict

# HEADER = {} # Removed initial empty dict

# Hint: REPO_LIST contains the GitHub repositories where manifests are stored
REPO_LIST = [
    "SteamAutoCracks/ManifestHub",
    "ikun0014/ManifestHub",
    "Auiowu/ManifestAutoUpdate",
    "tymolu233/ManifestAutoUpdate-fix",
]

# CLIENT is created within the AsyncWorker now
# CLIENT = httpx.AsyncClient(verify=False)