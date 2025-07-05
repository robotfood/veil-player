import os
import subprocess
import signal
import threading
import time
import requests
import xmltodict
import logging
from flask import Flask, jsonify, Response, render_template, abort

from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# --- Globals for state management ---
iptv_channels = []
vpn_process = None
vpn_lock = threading.Lock()

# --- VPN Management ---

def start_vpn():
    """Starts the OpenVPN client in a separate process."""
    global vpn_process
    with vpn_lock:
        if vpn_process and vpn_process.poll() is None:
            app.logger.info("VPN is already running.")
            return True, "VPN is already running."

        vpn_config = app.config.get('VPN_CONFIG_PATH')
        auth_file = app.config.get('VPN_AUTH_FILE')

        if not vpn_config or not os.path.exists(vpn_config):
            app.logger.error("VPN config file not found or not configured.")
            return False, "VPN config file not found or not configured."

        command = ['sudo', 'openvpn', '--config', vpn_config]
        if auth_file and os.path.exists(auth_file):
            command.extend(['--auth-user-pass', auth_file])

        try:
            app.logger.info("Starting VPN with command: %s", " ".join(command))
            # Using preexec_fn to create a new process group
            vpn_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
            # A small delay to check for immediate errors
            time.sleep(3)
            if vpn_process.poll() is not None:
                # Process terminated quickly, likely an error
                stdout, stderr = vpn_process.communicate()
                error_message = stderr.decode().strip()
                app.logger.error("Failed to start VPN: %s", error_message)
                return False, f"Failed to start VPN: {error_message}"
            app.logger.info("VPN connection initiated.")
            return True, "VPN connection initiated."
        except Exception as e:
            app.logger.error("Exception on starting VPN: %s", e)
            return False, f"Exception on starting VPN: {e}"

def stop_vpn():
    """Stops the OpenVPN client process."""
    global vpn_process
    with vpn_lock:
        if vpn_process and vpn_process.poll() is None:
            try:
                app.logger.info("Stopping VPN process.")
                # Kill the entire process group
                os.killpg(os.getpgid(vpn_process.pid), signal.SIGTERM)
                vpn_process.wait(timeout=5)
                vpn_process = None
                app.logger.info("VPN connection terminated.")
                return True, "VPN connection terminated."
            except ProcessLookupError:
                vpn_process = None
                app.logger.warning("VPN process was not found, assumed stopped.")
                return True, "VPN process was not found, assumed stopped."
            except Exception as e:
                app.logger.error("Error stopping VPN: %s", e)
                return False, f"Error stopping VPN: {e}"
        app.logger.info("VPN is not running.")
        return True, "VPN is not running."

def get_vpn_status():
    """Checks the status of the VPN connection."""
    with vpn_lock:
        if vpn_process and vpn_process.poll() is None:
            return "RUNNING"
        return "STOPPED"

# --- IPTV Service ---
def parse_extinf_line(line):
    """Parse EXTINF line to extract channel name."""
    # Extract the channel name (everything after the last comma)
    if ',' in line:
        return line.split(',', 1)[1].strip()
    return 'Unknown Channel'

def fetch_and_parse_iptv_data():
    """Fetches and parses the IPTV M3U playlist."""
    app.logger.info("Fetching IPTV data...")
    global iptv_channels
    playlist_url = app.config.get('IPTV_PLAYLIST_URL')
    if not playlist_url:
        app.logger.warning("IPTV_PLAYLIST_URL not set in config.")
        return []

    try:
        app.logger.info("Fetching IPTV playlist from %s", playlist_url)
        response = requests.get(playlist_url, timeout=10)
        app.logger.info(f"Received status code: {response.status_code}")
        response.raise_for_status()
        
        # Parse M3U playlist
        channels = []
        lines = response.text.splitlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('#EXTINF:'):
                # Parse the EXTINF line to get channel name
                channel_name = parse_extinf_line(line)
                
                # The next line should be the stream URL
                if i + 1 < len(lines):
                    stream_url = lines[i + 1].strip()
                    if stream_url and not stream_url.startswith('#'):
                        channel = {
                            'id': str(len(channels) + 1),
                            'name': channel_name,
                            'url': stream_url
                        }
                        channels.append(channel)
                        i += 1  # Skip the URL line in next iteration
            i += 1
        
        iptv_channels = channels
        app.logger.info("Successfully loaded %d channels from M3U playlist.", len(channels))
        return channels

    except requests.RequestException as e:
        app.logger.error("Error fetching IPTV playlist: %s", e)
    except Exception as e:
        app.logger.error("Error parsing IPTV playlist: %s", e)
    return []


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html', channels=iptv_channels, vpn_status=get_vpn_status())

@app.route('/api/channels')
def get_channels_api():
    return jsonify(iptv_channels)

@app.route('/api/vpn/connect', methods=['POST'])
def vpn_connect():
    success, message = start_vpn()
    return jsonify({'success': success, 'message': message})

@app.route('/api/vpn/disconnect', methods=['POST'])
def vpn_disconnect():
    success, message = stop_vpn()
    return jsonify({'success': success, 'message': message})

@app.route('/api/vpn/status')
def vpn_status_api():
    return jsonify({'status': get_vpn_status()})

@app.route('/stream/<channel_id>')
def stream_proxy(channel_id):
    """
    This is a simplified proxy. A robust implementation would handle stream
    chunking, headers, and error handling more gracefully.
    """
    channel = next((c for c in iptv_channels if c['id'] == channel_id), None)
    if not channel:
        app.logger.warning("Stream requested for non-existent channel ID: %s", channel_id)
        abort(404, description="Channel not found")

    # This is where you would use the REAL stream URL
    stream_url = channel.get('url') # Using placeholder URL for now
    
    # In a real scenario, you would replace the placeholder with a real URL from your M3U
    # For now, this will likely fail, but it demonstrates the proxy mechanism.
    if "placeholder.stream" in stream_url:
        app.logger.error("Attempted to stream placeholder URL for channel: %s", channel_id)
        abort(501, description="Stream URL is a placeholder. Configure your channel source.")

    try:
        app.logger.info("Proxying stream for channel %s from %s", channel_id, stream_url)
        req = requests.get(stream_url, stream=True, timeout=10)
        return Response(req.iter_content(chunk_size=1024), content_type=req.headers['content-type'])
    except requests.RequestException as e:
        app.logger.error("Failed to fetch stream from source for channel %s: %s", channel_id, e)
        abort(502, description=f"Failed to fetch stream from source: {e}")

# Configure logging to be applied globally
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fetch initial channel data when the app starts up
with app.app_context():
    fetch_and_parse_iptv_data()

if __name__ == '__main__':
    # This block is for running the app directly with `python app.py`
    # It is not executed when using `flask run` or a production server like Gunicorn.
    app.logger.info("Starting Flask development server via app.run()...")
    app.run(host='0.0.0.0', port=5000, debug=True)
