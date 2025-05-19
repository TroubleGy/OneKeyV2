# OneKeyV2

OneKeyV2 is an upgraded version of the original OneKey tool, designed to simplify the process of unlocking Steam games using SteamTools or GreenLuma. This project is based on the original OneKey by ikun0014, but includes stability improvements, better UX, and an auto-update system.

---

## Features

- GitHub integration for downloading manifests and decryption keys
- Supports both SteamTools and GreenLuma
- Auto-update support (configurable)
- Console + logfile logging system
- Zero setup: `config.json` is created automatically
- SteamDB integration: shows game name & SteamDB link for the given AppID

---

## Versions

- OneKeyV2 (our version): `v1.12.1` by [TroubleGy](https://github.com/TroubleGy)
- Original OneKey: `v1.4.7` by [ikun0014](https://github.com/ikunshare/)

---

## Installation

### For Users (EXE Version)

1. Download `OneKeyV2.exe` from [Releases](https://github.com/TroubleGy/OnekeyV2/releases)
2. Run it — `config.json` will be created automatically
3. Open `config.json` and insert your GitHub Personal Token (optional, but highly recommended)
4. Run `OneKeyV2.exe` again and follow the prompts

### For Developers

1. Clone the repository: git clone https://github.com/TroubleGy/OnekeyV2.git
2. Install dependencies: pip install -r requirements.txt
3. Run the tool: python main.py

---

## Configuration

`config.json` will be auto-generated on first run. Below are the available options:

- `Github_Personal_Token`: Optional GitHub token to avoid API rate limits
- `Custom_Steam_Path`: Leave empty to auto-detect; or specify Steam path manually
- `Debug_Mode`: Enables detailed console logs (`true` / `false`)
- `Logging_Files`: Enables saving logs to `./logs` folder (`true` / `false`)
- `Auto_Update`: Enables update checks (`true` / `false`)
  - `Check_Interval`: How often to check in hours

---

## Usage

1. Launch OneKeyV2
2. Enter the Steam AppID for the game
3. After entering the App ID, the program automatically detects the game's name using SteamDB API
4. You will see the game's name and a link to its SteamDB page for verification
5. Select unlock tool (SteamTools or GreenLuma)
6. Restart Steam and enjoy the game

---

## Notes

- Windows 10/11 only
- GitHub token is strongly recommended when using VPN / unstable IPs
- Steam must be installed and unlocked using SteamTools or GreenLuma
- Do **not** sell this tool under any circumstances

---

## License

This project is licensed under the MIT License.  
See the `LICENSE` file for full license text.

---

## Special Thanks

- [ikun0014](https://github.com/ikunshare/Onekey) for the original OneKey
- GitHub and the open-source community for the libraries
- [SteamDB](https://steamdb.info/) for providing free access to Steam game metadata  

---

Project proudly maintained by [TroubleGy](https://github.com/TroubleGy)
