# VeilPlayer

A lightweight IPTV player with built-in VPN support, built with Python Flask.

## Features

- **IPTV Playback**: Stream IPTV channels directly in your browser or external player
- **M3U Playlist Support**: Load channels from standard M3U playlists
- **Built-in VPN**: Integrated OpenVPN client for secure, private streaming
- **Web Interface**: Simple and intuitive interface for browsing and playing channels
- **Lightweight**: Minimal resource usage, runs on any modern device

## Prerequisites

- Python 3.7+
- `openvpn` command-line client installed on the system.
  - On Debian/Ubuntu: `sudo apt-get install openvpn`
  - On macOS (with Homebrew): `brew install openvpn`
- `sudo` access for the user running the application, as `openvpn` often requires elevated privileges to modify network routes. You can configure `sudoers` for passwordless execution if desired.

## Setup

1.  **Clone the repository or download the files.**

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure the application:**
    - Copy `.env.example` to `.env`:
      ```bash
      cp .env.example .env
      ```
    - Edit the `.env` file with your specific configuration:
      - `IPTV_XML_URL`: The URL to your IPTV provider's XMLTV file.
      - `VPN_CONFIG_PATH`: The absolute path to your `.ovpn` file.
      - `VPN_AUTH_FILE`: (Optional) The absolute path to a file containing your VPN username on the first line and password on the second. This is required if your `.ovpn` file uses `auth-user-pass` without a specific file path.

4.  **Run the application:**
    ```bash
    # For development
    ./venv/bin/flask run --host=0.0.0.0 --port=5001 --debug

    # For production (recommended)
    gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
    ```

## How It Works

### IPTV
- On startup, the application fetches the XML file specified in `IPTV_XML_URL`.
- It parses the file to get a list of channels.
- **Note**: The current implementation has a **placeholder** for stream URLs. You will need to modify the `fetch_and_parse_iptv_data` function in `app.py` to correctly map your channel IDs to actual stream URLs (e.g., from an M3U playlist).

### VPN
- The web UI provides buttons to connect and disconnect the VPN.
- These actions call API endpoints that use Python's `subprocess` module to run the `openvpn` command with the provided configuration.
- The application requires `sudo` to run `openvpn`. You may be prompted for a password in the console where the app is running unless you have configured passwordless sudo for this command.

### Proxy
- The `/stream/<channel_id>` endpoint looks up the channel's stream URL and acts as a proxy, fetching the stream from the source and relaying it to the client.
- This allows clients on your local network to access the streams through this application, even if the VPN is active on the server running the app.

## API Endpoints

- `GET /`: The main HTML web interface.
- `GET /api/channels`: Returns a JSON list of available channels.
- `POST /api/vpn/connect`: Initiates the VPN connection.
- `POST /api/vpn/disconnect`: Terminates the VPN connection.
- `GET /api/vpn/status`: Returns the current status of the VPN (`RUNNING` or `STOPPED`).
- `GET /stream/<channel_id>`: Proxies the video stream for the given channel ID.
