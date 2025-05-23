import os
import sys
import time
import asyncio
import traceback
from typing import Any, Tuple, List, Dict
from pathlib import Path
import httpx
import vdf
import logging
from tkinter import END
from common import variable
from common.variable import (
    REPO_LIST,
    load_config,
    get_steam_path,
    format_stack_trace,
    DEFAULT_CONFIG,
)

# CLIENT is now created and managed within AsyncWorker in common/gui.py
# from common.variable import CLIENT

# Import GUI and ConfigWindow and register_fonts
try:
    from common.gui import OneKeyGUI, ConfigWindow, register_fonts, GLOBAL_QSS
    from PyQt6.QtWidgets import QApplication, QDialog
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# Logging setup
class CustomFormatter(logging.Formatter):
    def format(self, record):
        # Remove extra information from error messages
        if record.exc_info:
            record.exc_text = str(record.exc_info[1])
        return super().format(record)

# Create formatter with Unicode support
formatter = CustomFormatter('%(message)s')

# Configure console output with Unicode support
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Configure logger
LOG = logging.getLogger("OnekeyV2")
LOG.setLevel(logging.INFO)
LOG.addHandler(console_handler)

# Hint: LOCK is used to prevent concurrent access to shared resources in async operations
# LOCK = asyncio.Lock() # Keep LOCK if needed for other async operations not using client
DEFAULT_REPO = REPO_LIST[0]

# Versions
ORIGINAL_VERSION = "1.4.7"  # Original OneKey version by ikun0014
OUR_VERSION = "1.21.0"        # Our OneKeyV2 version by TroubleGy

def get_banner_and_info() -> list:
    banner = r'''
    _____   __   _   _____   _   _    _____  __    __ 
   /  _  \ |  \ | | | ____| | | / /  | ____| \ \  / /\n   | | | | |   \| | | |__   | |/ /   | |__    \ \/ / \n   | | | | | |\   | |  __|  | |\ \   |  __|    \  /  \n   | |_| | | | \  | | |___  | | \ \  | |___    / /   \n   \_____/ |_|  \_| |_____| |_|  \_\ |_____|  /_/    \n    '''
    info = [
        banner,
        f"OneKeyV2 | Author: TroubleGy | Version: {OUR_VERSION} | GitHub: https://github.com/TroubleGy",
        f"Based on OneKey | Original Author: ikun0014 | Original Version: {ORIGINAL_VERSION} | Website: ikunshare.com",
        "Project Repository: GitHub: https://github.com/TroubleGy/OneKeyV2 (coming soon)",
        "TroubleGy | Reselling is strictly prohibited",
        "Note: Ensure you have Windows 10/11 and Steam properly configured; SteamTools/GreenLuma",
        "If using a VPN, you must configure a GitHub token, as your IP may not be trusted"
    ]
    return info

async def check_location(client: httpx.AsyncClient) -> bool:
    """Check if the user is located in mainland China."""
    try:
        req = await client.get("https://mips.kugou.com/check/iscn?&format=json", timeout=5)
        body = req.json()
        is_cn = bool(body["flag"])
        if not is_cn:
            LOG.info(f"You're outside mainland China ({body['country']}). Switching to GitHub CDN.")
            variable.IS_CN = False
            return False
        else:
            variable.IS_CN = True
            return True
    except (httpx.ConnectTimeout, httpx.ReadTimeout):
        LOG.warning("Location check timed out. Assuming China mainland.")
        variable.IS_CN = True
        return True
    except Exception as e:
        LOG.warning(f"Failed to check region: {format_stack_trace(e)}")
        variable.IS_CN = True
        return True


async def check_rate_limit(client: httpx.AsyncClient, headers: Dict[str, str]) -> None:
    """Check GitHub API rate limits."""
    url = "https://api.github.com/rate_limit"
    try:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        rate_limit = response.json().get("rate", {})
        remaining_requests = rate_limit.get("remaining", 0)
        reset_time = rate_limit.get("reset", 0)
        reset_time_formatted = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(reset_time)
        )
        LOG.info(f"Remaining GitHub API requests: {remaining_requests}")
        if remaining_requests == 0:
            LOG.warning(
                f"GitHub API request limit exhausted. It will reset at {reset_time_formatted}. "
                "Consider adding a token to your config file."
            )
    except KeyboardInterrupt:
        LOG.info("Program terminated by user.")
    except httpx.ConnectError as e:
        LOG.error(f"Failed to check GitHub API rate limit: {format_stack_trace(e)}")
    except httpx.ConnectTimeout as e:
        LOG.error(f"GitHub API rate limit check timed out: {format_stack_trace(e)}")
    except Exception as e:
        LOG.error(f"An error occurred: {format_stack_trace(e)}")


async def get_latest_repo_info(client: httpx.AsyncClient, repos: List[str], app_id: str, headers: Dict[str, str]) -> Tuple[str, str]:
    """Get the latest repository information for a given app ID."""
    latest_date = None
    selected_repo = None
    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/branches/{app_id}"
        response = await client.get(url, headers=headers)
        response_json = response.json()
        if response_json and "commit" in response_json:
            date = response_json["commit"]["commit"]["author"]["date"]
            if latest_date is None or date > latest_date:
                latest_date = date
                selected_repo = repo
    if selected_repo is None or latest_date is None:
        raise ValueError(f"No valid repository found for app ID {app_id}")
    return selected_repo, latest_date

async def get_game_name(client: httpx.AsyncClient, app_id: str) -> str | None:
    """Returns the game's name from Steam store API"""
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get(app_id, {}).get("success"):
            return data[app_id]["data"]["name"]
    except Exception as e:
        LOG.warning(f"Failed to fetch game name: {format_stack_trace(e)}")
    return None

async def get_game_developers(client: httpx.AsyncClient, app_id: str) -> str | None:
    """Returns the game's developers from Steam store API"""
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get(app_id, {}).get("success"):
            return data[app_id]["data"]["developers"]
    except Exception as e:
        LOG.warning(f"Failed to fetch game developers: {format_stack_trace(e)}")
    return None

async def get_game_publishers(client: httpx.AsyncClient, app_id: str) -> str | None:
    """Returns the game's publishers from Steam store API"""
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get(app_id, {}).get("success"):
            return data[app_id]["data"]["publishers"]
    except Exception as e:
        LOG.warning(f"Failed to fetch game publishers: {format_stack_trace(e)}")
    return None

async def get_game_icon(client: httpx.AsyncClient, app_id: str) -> bytes | None:
    """Returns the game's icon from Steam image server"""
    # Reverting to a smaller capsule image for potentially broader compatibility
    url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/capsule_sm_120.jpg"
    try:
        LOG.debug(f"Attempting to fetch game icon from {url}")
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        LOG.warning(f"Failed to fetch game icon for {app_id}: {format_stack_trace(e)}")
        return None

async def handle_depot_files(
    repos: List[str], app_id: str, steam_path: Path, gui, client: httpx.AsyncClient
) -> Tuple[List[Tuple[str, str]], Dict[str, List[str]]]:
    """Handle depot files for a given app ID."""
    # Check if steam_path is valid
    if steam_path is None:
        gui.set_status("Error: Steam path is not configured.", error=True)
        LOG.error("Steam path is None in handle_depot_files.")
        return [], {}

    collected = []
    depot_map = {}
    try:
        gui.set_status("Fetching latest repository info...", error=False)
        selected_repo, latest_date = await get_latest_repo_info(client, repos, app_id, headers=variable.HEADER)

        branch_url = f"https://api.github.com/repos/{selected_repo}/branches/{app_id}"
        branch_res = await client.get(branch_url, headers=variable.HEADER)
        branch_res.raise_for_status()

        tree_url = branch_res.json()["commit"]["commit"]["tree"]["url"]
        tree_res = await client.get(tree_url)
        tree_res.raise_for_status()

        depot_cache = steam_path / "depotcache"
        depot_cache.mkdir(exist_ok=True)

        gui.set_status(f"Selected manifest repository: {selected_repo}", error=False)
        gui.set_status(f"Last update of this manifest branch: {latest_date}", error=False)

        for item in tree_res.json()["tree"]:
            file_path = str(item["path"])
            if file_path.endswith(".manifest"):
                save_path = depot_cache / file_path
                if save_path.exists():
                    LOG.warning(f"Manifest already exists: {save_path}")
                    continue
                gui.set_status(f"Downloading manifest: {file_path}...", error=False)
                content = await fetch_files(
                    client,
                    branch_res.json()["commit"]["sha"], file_path, selected_repo
                )
                gui.set_status(f"Manifest downloaded successfully: {file_path}", error=False)
                with open(save_path, "wb") as f:
                    f.write(content)
            elif "key.vdf" in file_path.lower():
                gui.set_status(f"Downloading key file: {file_path}...", error=False)
                key_content = await fetch_files(
                    client,
                    branch_res.json()["commit"]["sha"], file_path, selected_repo
                )
                gui.set_status(f"Key file downloaded successfully: {file_path}", error=False)
                collected.extend(parse_key(key_content))

        for item in tree_res.json()["tree"]:
            if not item["path"].endswith(".manifest"):
                continue

            filename = Path(item["path"]).stem
            if "_" not in filename:
                continue

            depot_id, manifest_id = filename.replace(".manifest", "").split("_", 1)
            if not (depot_id.isdigit() and manifest_id.isdigit()):
                continue

            depot_map.setdefault(depot_id, []).append(manifest_id)

        for depot_id in depot_map:
            depot_map[depot_id].sort(key=lambda x: int(x), reverse=True)

    except httpx.HTTPStatusError as e:
        gui.set_status(f"HTTP error while handling files: {e.response.status_code}", error=True)
        LOG.error(f"HTTP error: {e.response.status_code}") # Keep in console
    except Exception as e:
        gui.set_status(f"Failed to process files: {str(e)}", error=True)
        LOG.error(f"Failed to process files: {str(e)}") # Keep in console
    return collected, depot_map


async def fetch_files(client: httpx.AsyncClient, sha: str, path: str, repo: str) -> bytes:
    """Fetch files from GitHub with retry logic.
    
    Args:
        sha (str): The commit SHA to fetch from
        path (str): The file path to fetch
        repo (str): The repository name
        
    Returns:
        bytes: The file contents
        
    Raises:
        Exception: If all retries fail or if the file cannot be downloaded
    """
    if variable.IS_CN:
        url_list = [
            f"https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}",
            f"https://raw.gitmirror.com/{repo}/{sha}/{path}",
            f"https://raw.dgithub.xyz/{repo}/{sha}/{path}",
            f"https://gh.akass.cn/{repo}/{sha}/{path}",
        ]
    else:
        url_list = [f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"]

    retry_count = variable.CONFIG.get("network", {}).get("retry_count", 3)
    timeout = variable.CONFIG.get("network", {}).get("timeout", 30)
    retry_delay = variable.CONFIG.get("network", {}).get("retry_delay", 1)
    last_error = None

    while retry_count > 0:
        for url in url_list:
            try:
                LOG.debug(f"Attempting to fetch {path} from {url}")
                response = await client.get(url, headers=variable.HEADER, timeout=timeout)
                response.raise_for_status()
                content = response.read()
                LOG.info(f"Successfully downloaded {path} from {url}") # Keep success message in console
                return content
            except KeyboardInterrupt:
                LOG.info("Program terminated by user.")
                raise
            except httpx.ConnectError as e:
                last_error = e
                LOG.error(f"Connection error while fetching {path} from {url}: {str(e)}")
            except httpx.ConnectTimeout as e:
                last_error = e
                LOG.error(f"Connection timeout while fetching {path} from {url}: {str(e)}")
            except httpx.HTTPStatusError as e:
                last_error = e
                LOG.error(f"HTTP error {e.response.status_code} while fetching {path} from {url}")
            except Exception as e:
                last_error = e
                LOG.error(f"Unexpected error while fetching {path} from {url}: {str(e)}")

        retry_count -= 1
        if retry_count > 0:
            LOG.warning(f"Retries remaining: {retry_count} for {path}")
            await asyncio.sleep(retry_delay)

    error_msg = f"Failed to download {path} after all retries. Last error: {str(last_error)}"
    LOG.error(error_msg)
    raise Exception(error_msg) # Exception will be caught and status updated in main_gui


def parse_key(content: bytes) -> List[Tuple[str, str]]:
    """Parse decryption keys from VDF content."""
    try:
        depots = vdf.loads(content.decode("utf-8"))["depots"]
        return [(d_id, d_info["DecryptionKey"]) for d_id, d_info in depots.items()]
    except Exception as e:
        LOG.error(f"Failed to parse keys: {str(e)}")
        return []


def setup_unlock(
    depot_data: List[Tuple[str, str]],
    app_id: str,
    tool_choice: int,
    depot_map: Dict[str, List[str]],
    gui
) -> bool:
    """Set up unlocking configuration based on the chosen tool."""
    gui.set_status("Applying unlock configuration...", error=False)
    if tool_choice == 1:
        success = setup_steamtools(depot_data, app_id, depot_map)
        if success:
            gui.set_status("SteamTools configuration applied.", error=False)
        else:
            gui.set_status("SteamTools configuration failed.", error=True)
        return success
    elif tool_choice == 2:
        success = setup_greenluma(depot_data)
        if success:
            gui.set_status("GreenLuma configuration applied.", error=False)
        else:
            gui.set_status("GreenLuma configuration failed.", error=True)
        return success
    else:
        gui.set_status("Error: Invalid tool choice.", error=True)
        LOG.error("Invalid tool choice.") # Keep in console
        return False


def setup_steamtools(depot_data: List[Tuple[str, str]], app_id: str, depot_map: Dict[str, List[str]]) -> bool:
    """Set up SteamTools configuration."""
    st_path = variable.STEAM_PATH / "config" / "stplug-in"
    st_path.mkdir(exist_ok=True)

    # Input is now handled by the GUI worker and passed back
    # choice = input(
    #     "Do you want to lock the version (recommended for SteamAutoCracks/ManifestHub repositories)? (y/n): "
    # ).lower()

    # Assuming input is handled outside this function or passed in
    # This function now only performs the setup based on received depot_data and app_id

    lua_content = f'addappid({app_id}, 1, "None")\n'
    for d_id, d_key in depot_data:
        # versionlock logic would depend on the input received by the worker
        # For simplicity, let's assume versionlock is always False for now, or passed as a param
        versionlock = False # Needs to be passed or handled differently
        if versionlock:
            for manifest_id in depot_map[d_id]:
                lua_content += f'addappid({d_id}, 1, "{d_key}")\nsetManifestid({d_id},"{manifest_id}")\n'
        else:
            lua_content += f'addappid({d_id}, 1, "{d_key}")\n'

    lua_file = st_path / f"{app_id}.lua"
    try:
        with open(lua_file, "w") as f:
            f.write(lua_content)
        LOG.info(f"SteamTools config saved to {lua_file}") # Keep in console
        return True
    except Exception as e:
        LOG.error(f"Failed to write SteamTools config: {format_stack_trace(e)}")
        return False


def setup_greenluma(depot_data: List[Tuple[str, str]]) -> bool:
    """Set up GreenLuma configuration."""
    applist_dir = variable.STEAM_PATH / "AppList"
    applist_dir.mkdir(exist_ok=True)

    try:
        for f in applist_dir.glob("*.txt"):
            f.unlink()

        for idx, (d_id, _) in enumerate(depot_data, 1):
            (applist_dir / f"{idx}.txt").write_text(str(d_id))

        config_path = variable.STEAM_PATH / "config" / "config.vdf"
        with open(config_path, "r+") as f:
            content = vdf.loads(f.read())
            content.setdefault("depots", {}).update(
                {d_id: {"DecryptionKey": d_key} for d_id, d_key in depot_data}
            )
            f.seek(0)
            f.write(vdf.dumps(content))
        LOG.info("GreenLuma config updated.") # Keep in console
        return True
    except Exception as e:
        LOG.error(f"Failed to update GreenLuma config: {format_stack_trace(e)}")
        return False


async def check_for_updates(client: httpx.AsyncClient) -> None:
    """Check for updates from GitHub Releases."""
    try:
        LOG.info("Checking GitHub for new release...") # Keep in console

        url = "https://api.github.com/repos/TroubleGy/OneKeyV2/releases/latest"
        response = await client.get(url, headers=variable.HEADER)

        if response.status_code == 404:
            LOG.warning("Update check: Version not found.") # Keep in console
            return

        response.raise_for_status()
        data = response.json()

        raw_tag = data.get("tag_name", "")
        latest_version = (
            raw_tag[1:] if raw_tag.lower().startswith("v") and len(raw_tag) > 1 else raw_tag
        )

        download_url = next(
            (asset["browser_download_url"] for asset in data.get("assets", []) if asset["name"].endswith(".exe")),
            None
        )

        if latest_version != OUR_VERSION:
            LOG.warning(f"\n\nOneKeyV2 is outdated. Current: {OUR_VERSION}  |  Latest: {latest_version}") # Keep in console
            # Input is handled by GUI worker
            # choice = input("Update now? (y/n): ").strip().lower()
            # if choice == "y" and download_url:
            #     await download_new_version(client, download_url) # Pass client here
            # else:
            #     LOG.info("Skipping update.")

        else:
            LOG.info("✅ You are running the latest version.") # Keep in console

    except Exception as e:
        LOG.error(f"Auto-update check failed: {format_stack_trace(e)}") # Keep in console

async def download_new_version(client: httpx.AsyncClient, url: str):
    """Download and save updated .exe file"""
    LOG.info("Downloading latest version...") # Keep in console

    new_file = "OneKeyV2_update.exe"

    try:
        r = await client.get(url, timeout=60, follow_redirects=True)
        r.raise_for_status()
        with open(new_file, "wb") as f:
            f.write(r.content)
        LOG.info(f"✅ Downloaded update: {new_file}") # Keep in console
        LOG.info("Please close this program and manually run OneKeyV2_update.exe") # Keep in console
    except Exception as e:
        LOG.error(f"Update failed: {format_stack_trace(e)}") # Keep in console


async def main_gui(app_id: str, gui, stage: str, client: httpx.AsyncClient):
    # Clear previous game info and hide buttons at the start of any new process (Modified)
    # gui.clear_game_info() # Removed from here
    gui.hide_start_button()
    gui.hide_open_steamdb_button()

    if stage == "view":
        # Clear game info only when starting a new view process
        gui.clear_game_info()
        gui.set_status("Fetching game info...", error=False)
        try:
            app_id_list = list(filter(str.isdigit, app_id.strip().split("-")))
            if not app_id_list:
                gui.set_status("Error: Invalid AppID", error=True)
                LOG.error("Invalid AppID.") # Keep in console
                gui.clear_game_info() # Keep clear here for invalid input
                gui.hide_start_button()
                return False, None, None

            app_id = app_id_list[0]
            game_name = await get_game_name(client, app_id)
            game_developers = await get_game_developers(client, app_id)
            game_publishers = await get_game_publishers(client, app_id)

            # LOG.info(f"Debug: Fetched game_name: {game_name}") # Removed verbose logging

            game_info = {
                "App ID": app_id,
                "App Type": "Unknown",
                "Developer": "Unknown",
                "Publisher": "Unknown",
                "Supported Systems": "Windows",
                "Technologies": "Unknown",
                "Last Changenumber": "N/A",
                "Last Record Update": "N/A",
                "Release Date": "N/A"
            }

            if game_name:
                steamdb_url = f"https://steamdb.info/app/{app_id}/"
                LOG.info(f"Game: {game_name}") # Keep in console
                LOG.info(f"SteamDB: {steamdb_url}") # Keep in console
                gui.set_status(f"Found game: {game_name}", error=False)
                game_info["App Type"] = "Application"
                game_info["Game Name"] = game_name
                if game_developers:
                    game_info["Developers"] = game_developers
                if game_publishers:
                    game_info["Publishers"] = game_publishers

                # Fetch game icon
                gui.set_status("Fetching game icon...", error=False)
                game_icon_data = await get_game_icon(client, app_id)
                if game_icon_data:
                    game_info["IconData"] = game_icon_data
                    gui.set_status("Game icon fetched.", error=False)
                else:
                    gui.set_status("Could not fetch game icon.", error=False)
            else:
                gui.set_status("Warning: AppID not found on Steam", error=False)
                LOG.warning("AppID not found on Steam. Cannot fetch detailed info.") # Keep in console
                gui.clear_game_info()
                gui.hide_start_button()
                return False, None, None

            gui.set_game_info(game_info)
            gui.set_status("Game info fetched.", error=False)
            return True, app_id, steamdb_url

        except Exception as e:
            gui.set_status(f"Error fetching info! {format_stack_trace(e)}", error=True)
            LOG.error(f"Error fetching game info: {format_stack_trace(e)}") # Keep in console
            gui.clear_game_info()
            gui.hide_start_button()
            return False, None, None

    elif stage == "unlock":
        gui.set_status("Starting unlock process...", error=False)
        try:
            app_id_list = list(filter(str.isdigit, app_id.strip().split("-")))
            if not app_id_list:
                 gui.set_status("Error: Invalid AppID", error=True)
                 LOG.error("Invalid AppID.") # Keep in console
                 gui.clear_game_info() # Keep clear here for invalid input
                 return False, None, None
            app_id = app_id_list[0]
            gui.set_status("Checking location...", error=False)
            await check_location(client) # This function logs to console
            gui.set_status("Checking GitHub rate limit...", error=False)
            await check_rate_limit(client, variable.HEADER) # This function logs to console
            gui.set_status("Checking for updates...", error=False)
            await check_for_updates(client) # This function logs to console
            gui.set_status("Handling depot files...", error=False)
            depot_data, depot_map = await handle_depot_files(REPO_LIST, app_id, variable.STEAM_PATH, gui, client) # Pass gui and client here

            if not depot_data or not depot_map:
                gui.set_status("Error: No manifests found", error=True)
                LOG.error("No manifests found for this game.") # Keep in console
                return False, None, None

            tool_choice = gui.get_tool_choice()
            if setup_unlock(depot_data, app_id, tool_choice, depot_map, gui): # Pass gui here
                gui.set_status("Configuration completed successfully! Restart Steam to apply changes.", error=False)
                LOG.info("Configuration completed successfully! Restart Steam to apply changes.") # Keep in console
                return True, app_id, None
            else:
                gui.set_status("Error: Configuration failed.", error=True)
                LOG.error("Configuration failed.") # Keep in console
                return False, app_id, None
        except Exception as e:
            gui.set_status(f"Error during unlock! {format_stack_trace(e)}", error=True)
            LOG.error(f"Error during unlock: {format_stack_trace(e)}") # Keep in console
            return False, app_id, None


if __name__ == "__main__":
    # Logging setup for console output (kept)
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    if GUI_AVAILABLE:
        # Create QApplication instance once
        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        # Apply global stylesheet
        app.setStyleSheet(GLOBAL_QSS) # Apply QSS to the application instance

        # Register custom fonts after QApplication is created
        register_fonts() # Call the function here

        # Initial config load check
        initial_config = load_config()
        config = None # Variable to hold the final config

        if initial_config is None:
            # Config is missing or corrupted, show config window
            config_window = ConfigWindow()
            # Show dialog and wait for user interaction
            result = config_window.exec() # This runs a local event loop for the dialog

            if result == QDialog.DialogCode.Accepted: # Check if the dialog was accepted (Save button clicked)
                # Config was saved, reload it
                config = load_config()
                if config is None:
                    # Should not happen if save_config was successful, but handle defensively
                    print("Failed to load config after saving. Exiting.")
                    sys.exit(1) # Exit if config still can't be loaded
            else:
                # User cancelled config, exit the application
                sys.exit(0)
        else:
            # Config loaded successfully
            config = initial_config

        # Update global variables based on loaded config (using the single loaded config)
        variable.CONFIG = config
        variable.DEBUG_MODE = config.get("Debug_Mode", False)
        variable.LOG_FILE = config.get("Logging_Files", True)
        variable.GITHUB_TOKEN = str(config.get("Github_Personal_Token", ""))
        variable.STEAM_PATH = get_steam_path(config) # Use the function to get Path object
        variable.HEADER = {"Authorization": f"Bearer {variable.GITHUB_TOKEN}"} if variable.GITHUB_TOKEN else {}
        variable.AUTO_UPDATE = config.get("Auto_Update", {})

        # Check if essential config (like Steam Path) is still missing/invalid after config window
        if variable.STEAM_PATH is None:
             print("Error: Steam path is not configured correctly. Please edit config.json.")
             sys.exit(1)

        # Now show the main GUI window using the single QApplication instance
        window = OneKeyGUI(start_callback=main_gui, version=OUR_VERSION)
        window.show()

        # Run the main application event loop
        exit_code = app.exec() # This is the main application event loop
        sys.exit(exit_code)

    else:
        # GUI not available fallback
        print("GUI is not available. Please install PyQt6: pip install PyQt6") # Print to console fallback
        sys.exit(1)

    # The CLIENT is closed within the AsyncWorker now