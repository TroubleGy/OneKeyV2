import os
import sys
import time
import asyncio
import traceback
from typing import Any, Tuple, List, Dict
from pathlib import Path
import httpx
import vdf
from common import log, variable
from common.variable import (
    CLIENT,
    HEADER,
    STEAM_PATH,
    REPO_LIST,
    CONFIG,
    AUTO_UPDATE,
)

# Hint: LOCK is used to prevent concurrent access to shared resources in async operations
LOCK = asyncio.Lock()
LOG = log.log("OnekeyV2")
DEFAULT_REPO = REPO_LIST[0]

# Versions
ORIGINAL_VERSION = "1.4.7"  # Original OneKey version by ikun0014
OUR_VERSION = "1.00"        # Our OneKeyV2 version by TroubleGy


def init() -> None:
    """Initialize console output with a banner."""
    banner = r"""
    _____   __   _   _____   _   _    _____  __    __ 
   /  _  \ |  \ | | | ____| | | / /  | ____| \ \  / /
   | | | | |   \| | | |__   | |/ /   | |__    \ \/ / 
   | | | | | |\   | |  __|  | |\ \   |  __|    \  /  
   | |_| | | | \  | | |___  | | \ \  | |___    / /   
   \_____/ |_|  \_| |_____| |_|  \_\ |_____|  /_/    
    """
    LOG.info(banner)
    LOG.info(f"OneKeyV2 | Author: TroubleGy | Version: {OUR_VERSION} | GitHub: https://github.com/TroubleGy")
    LOG.info(f"Based on OneKey | Original Author: ikun0014 | Original Version: {ORIGINAL_VERSION} | Website: ikunshare.com")
    LOG.info("Project Repository: GitHub: https://github.com/TroubleGy/OnekeyV2 (coming soon)")
    LOG.warning("TroubleGy | Reselling is strictly prohibited")
    LOG.warning("Note: Ensure you have Windows 10/11 and Steam properly configured; SteamTools/GreenLuma")
    LOG.warning("If using a VPN, you must configure a GitHub token, as your IP may not be trusted")


async def check_location() -> bool:
    """Check if the user is located in mainland China."""
    try:
        req = await CLIENT.get("https://mips.kugou.com/check/iscn?&format=json", timeout=5)
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


def format_stack_trace(exception: Exception) -> str:
    """Format the stack trace of an exception."""
    stack_trace = traceback.format_exception(
        type(exception), exception, exception.__traceback__
    )
    return "".join(stack_trace)


async def check_rate_limit(headers: Dict[str, str]) -> None:
    """Check GitHub API rate limits."""
    url = "https://api.github.com/rate_limit"
    try:
        response = await CLIENT.get(url, headers=headers)
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


async def get_latest_repo_info(repos: List[str], app_id: str, headers: Dict[str, str]) -> Tuple[str, str]:
    """Get the latest repository information for a given app ID."""
    latest_date = None
    selected_repo = None
    for repo in repos:
        url = f"https://api.github.com/repos/{repo}/branches/{app_id}"
        response = await CLIENT.get(url, headers=headers)
        response_json = response.json()
        if response_json and "commit" in response_json:
            date = response_json["commit"]["commit"]["author"]["date"]
            if latest_date is None or date > latest_date:
                latest_date = date
                selected_repo = repo
    if selected_repo is None or latest_date is None:
        raise ValueError(f"No valid repository found for app ID {app_id}")
    return selected_repo, latest_date

async def get_game_name(app_id: str) -> str | None:
    """Returns the game's name from Steam store API"""
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
    try:
        resp = await CLIENT.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get(app_id, {}).get("success"):
            return data[app_id]["data"]["name"]
    except Exception as e:
        LOG.warning(f"Failed to fetch game name: {format_stack_trace(e)}")
    return None


async def handle_depot_files(
    repos: List[str], app_id: str, steam_path: Path
) -> Tuple[List[Tuple[str, str]], Dict[str, List[str]]]:
    """Handle depot files for a given app ID."""
    collected = []
    depot_map = {}
    try:
        selected_repo, latest_date = await get_latest_repo_info(repos, app_id, headers=HEADER)

        branch_url = f"https://api.github.com/repos/{selected_repo}/branches/{app_id}"
        branch_res = await CLIENT.get(branch_url, headers=HEADER)
        branch_res.raise_for_status()

        tree_url = branch_res.json()["commit"]["commit"]["tree"]["url"]
        tree_res = await CLIENT.get(tree_url)
        tree_res.raise_for_status()

        depot_cache = steam_path / "depotcache"
        depot_cache.mkdir(exist_ok=True)

        LOG.info(f"Selected manifest repository: https://github.com/{selected_repo}")
        LOG.info(f"Last update of this manifest branch: {latest_date}")

        for item in tree_res.json()["tree"]:
            file_path = str(item["path"])
            if file_path.endswith(".manifest"):
                save_path = depot_cache / file_path
                if save_path.exists():
                    LOG.warning(f"Manifest already exists: {save_path}")
                    continue
                content = await fetch_files(
                    branch_res.json()["commit"]["sha"], file_path, selected_repo
                )
                LOG.info(f"Manifest downloaded successfully: {file_path}")
                with open(save_path, "wb") as f:
                    f.write(content)
            elif "key.vdf" in file_path.lower():
                key_content = await fetch_files(
                    branch_res.json()["commit"]["sha"], file_path, selected_repo
                )
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
        LOG.error(f"HTTP error: {e.response.status_code}")
    except Exception as e:
        LOG.error(f"Failed to process files: {str(e)}")
    return collected, depot_map


async def fetch_files(sha: str, path: str, repo: str) -> bytes:
    """Fetch files from GitHub with retry logic."""
    if variable.IS_CN:
        url_list = [
            f"https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}",
            f"https://raw.gitmirror.com/{repo}/{sha}/{path}",
            f"https://raw.dgithub.xyz/{repo}/{sha}/{path}",
            f"https://gh.akass.cn/{repo}/{sha}/{path}",
        ]
    else:
        url_list = [f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"]

    retry_count = 3  # Hardcoded retry count
    timeout = 30     # Hardcoded timeout

    while retry_count > 0:
        for url in url_list:
            try:
                response = await CLIENT.get(url, headers=HEADER, timeout=timeout)
                response.raise_for_status()
                return response.read()
            except KeyboardInterrupt:
                LOG.info("Program terminated by user.")
                raise
            except httpx.ConnectError as e:
                LOG.error(f"Failed to fetch {path}: Connection error - {str(e)}")
            except httpx.ConnectTimeout as e:
                LOG.error(f"Connection timeout for {url}: {str(e)}")

        retry_count -= 1
        LOG.warning(f"Retries remaining: {retry_count} for {path}")

    LOG.error(f"Exceeded maximum retries for {path}")
    raise Exception(f"Unable to download {path}")


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
) -> bool:
    """Set up unlocking configuration based on the chosen tool."""
    if tool_choice == 1:
        return setup_steamtools(depot_data, app_id, depot_map)
    elif tool_choice == 2:
        return setup_greenluma(depot_data)
    else:
        LOG.error("Invalid tool choice.")
        return False


def setup_steamtools(depot_data: List[Tuple[str, str]], app_id: str, depot_map: Dict[str, List[str]]) -> bool:
    """Set up SteamTools configuration."""
    st_path = STEAM_PATH / "config" / "stplug-in"
    st_path.mkdir(exist_ok=True)

    choice = input(
        "Do you want to lock the version (recommended for SteamAutoCracks/ManifestHub repositories)? (y/n): "
    ).lower()

    versionlock = choice == "y"

    lua_content = f'addappid({app_id}, 1, "None")\n'
    for d_id, d_key in depot_data:
        if versionlock:
            for manifest_id in depot_map[d_id]:
                lua_content += f'addappid({d_id}, 1, "{d_key}")\nsetManifestid({d_id},"{manifest_id}")\n'
        else:
            lua_content += f'addappid({d_id}, 1, "{d_key}")\n'

    lua_file = st_path / f"{app_id}.lua"
    with open(lua_file, "w") as f:
        f.write(lua_content)

    return True


def setup_greenluma(depot_data: List[Tuple[str, str]]) -> bool:
    """Set up GreenLuma configuration."""
    applist_dir = STEAM_PATH / "AppList"
    applist_dir.mkdir(exist_ok=True)

    for f in applist_dir.glob("*.txt"):
        f.unlink()

    for idx, (d_id, _) in enumerate(depot_data, 1):
        (applist_dir / f"{idx}.txt").write_text(str(d_id))

    config_path = STEAM_PATH / "config" / "config.vdf"
    with open(config_path, "r+") as f:
        content = vdf.loads(f.read())
        content.setdefault("depots", {}).update(
            {d_id: {"DecryptionKey": d_key} for d_id, d_key in depot_data}
        )
        f.seek(0)
        f.write(vdf.dumps(content))
    return True


async def check_for_updates() -> None:
    """Check for updates from GitHub Releases."""
    try:
        LOG.info("Checking GitHub for new release...")

        url = "https://api.github.com/repos/TroubleGy/OneKeyV2/releases/latest"
        response = await CLIENT.get(url, headers=HEADER)

        if response.status_code == 404:
            LOG.warning("Update check: Version not found.")
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
            LOG.warning(f"\n\nOneKeyV2 is outdated. Current: {OUR_VERSION}  |  Latest: {latest_version}")
            choice = input("Update now? (y/n): ").strip().lower()
            if choice == "y" and download_url:
                await download_new_version(download_url)
            else:
                LOG.info("Skipping update.")
        else:
            LOG.info("✅ You are running the latest version.")

    except Exception as e:
        LOG.error(f"Auto-update check failed: {format_stack_trace(e)}")

async def download_new_version(url: str):
    """Download and save updated .exe file"""
    LOG.info("Downloading latest version...")
    new_file = "OneKeyV2_update.exe"
    try:
        r = await CLIENT.get(url, timeout=60)
        r.raise_for_status()
        with open(new_file, "wb") as f:
            f.write(r.content)
        LOG.info(f"Downloaded update: {new_file}")
        LOG.info("Please close this program and manually run OneKeyV2_update.exe")
    except Exception as e:
        LOG.error(f"Update failed: {format_stack_trace(e)}")


async def main(app_id: str) -> bool:
    """Main function to handle the unlocking process."""
    app_id_list = list(filter(str.isdigit, app_id.strip().split("-")))
    if not app_id_list:
        LOG.error("Invalid App ID.")
        os.system("pause")
        return False

    app_id = app_id_list[0]

     # Fetch game name from Steam store
    game_name = await get_game_name(app_id)
    if game_name:
        steamdb_url = f"https://steamdb.info/app/{app_id}/"
        LOG.info(f"🔍 Game detected: {game_name}")
        LOG.info(f"🔗 SteamDB page: {steamdb_url}")
    else:
        LOG.warning("⚠ AppID not found on Steam. Continuing anyway.")

    try:
        await check_location()
        await check_rate_limit(HEADER)
        await check_for_updates()

        depot_data, depot_map = await handle_depot_files(REPO_LIST, app_id, STEAM_PATH)

        if not depot_data or not depot_map:
            LOG.error("No manifests found for this game.")
            os.system("pause")
            return False

        tool_choice = int(input("Select unlocking tool (1. SteamTools, 2. GreenLuma): "))

        if setup_unlock(depot_data, app_id, tool_choice, depot_map):
            LOG.info("Game unlocking configuration completed successfully!")
            LOG.info("Restart Steam to apply changes.")
        else:
            LOG.error("Configuration failed.")

        os.system("pause")
        return True
    except Exception as e:
        LOG.error(f"Runtime error: {format_stack_trace(e)}")
        os.system("pause")
        return False
    except KeyboardInterrupt:
        os.system("pause")
        return False
    finally:
        await CLIENT.aclose()


if __name__ == "__main__":
    try:
        init()

        # Try to read AppID from command-line first
        app_id = None
        if len(sys.argv) > 1:
            app_id = sys.argv[1].strip()
            LOG.info(f"App ID detected from arguments: {app_id}")
        else:
            try:
                # Attempt to read via input()
                app_id = input("Enter the game App ID: ").strip()
            except Exception:
                LOG.error("❌ Can't read App ID: No console or stdin attached.")
                LOG.warning("💡 Solution 1: Launch via terminal")
                LOG.warning("💡 Solution 2: Use:  OneKeyV2.exe 730")
                os.system("pause")
                sys.exit(1)

        if not app_id:
            LOG.error("No App ID provided.")
            os.system("pause")
            sys.exit(1)

        asyncio.run(main(app_id))

    except (asyncio.CancelledError, KeyboardInterrupt):
        os.system("pause")
    except Exception as e:
        LOG.error(f"Error: {format_stack_trace(e)}")
        os.system("pause")