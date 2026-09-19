# pip install flask requests colorama

import os
import sys
import json
import time
import threading
import concurrent.futures
import hashlib
import io
import logging
import re
import socket
import subprocess
import tempfile
from flask import Flask, request, jsonify
import requests
from colorama import init, Fore, Style

init(autoreset=True)

BASE_DIR = (
    os.path.dirname(os.path.abspath(sys.executable))
    if getattr(sys, "frozen", False)
    else os.path.dirname(os.path.abspath(__file__))
)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "spoofer.log")
APP_VERSION = "2.1.0"
UPDATE_MANIFEST_URL = os.environ.get("SPOOFER_UPDATE_URL", "")
DEFAULT_PORT = 5555
MAX_WORKERS = 6
MAX_ANIMATIONS = 500
MAX_ANIMATION_BYTES = 10 * 1024 * 1024
DOWNLOAD_TIMEOUT = (5, 30)
UPLOAD_TIMEOUT = (5, 60)
OPERATION_TIMEOUT = 120
RETRY_LIMIT = 3

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("maiks_spoofer")

class Config:
    def __init__(self):
        self.cookie = ""
        self.api_key = ""
        self.user_id = ""
        self.port = DEFAULT_PORT
        self.update_manifest_url = UPDATE_MANIFEST_URL
        self.load()
    
    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cookie = data.get('cookie', '')
                    self.api_key = data.get('api_key', '')
                    self.user_id = data.get('user_id', '')
                    self.update_manifest_url = data.get('update_manifest_url', UPDATE_MANIFEST_URL)
                    port = data.get('port', DEFAULT_PORT)
                    self.port = port if isinstance(port, int) and 1 <= port <= 65535 else DEFAULT_PORT
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                logger.warning("Could not load configuration: %s", error)
    
    def save(self):
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=BASE_DIR,
                prefix='config.', suffix='.tmp', delete=False
            ) as f:
                json.dump({
                    'cookie': self.cookie,
                    'api_key': self.api_key,
                    'user_id': self.user_id,
                    'port': self.port,
                    'update_manifest_url': self.update_manifest_url
                }, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                temporary_path = f.name
            os.replace(temporary_path, CONFIG_FILE)
        except OSError as error:
            logger.error("Could not save configuration: %s", error)
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)
    
    def is_first_run(self):
        return not os.path.exists(CONFIG_FILE) or (not self.cookie and not self.api_key)

config = Config()
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 128 * 1024
START_TIME = time.time()
server_thread = None
server_running = False
spoof_in_progress = False
spoof_state_lock = threading.Lock()

@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "Request is too large"}), 413

@app.errorhandler(Exception)
def handle_server_error(error):
    logger.exception("Unhandled local server error: %s", error)
    if spoof_in_progress:
        end_spoof()
    return jsonify({"error": "Local server error. Check spoofer.log"}), 500

def begin_spoof():
    global spoof_in_progress
    with spoof_state_lock:
        if spoof_in_progress:
            return False
        spoof_in_progress = True
        return True

def end_spoof():
    global spoof_in_progress
    with spoof_state_lock:
        spoof_in_progress = False

def mask_string(s, show_chars=5):
    if len(s) <= show_chars * 2:
        return "****"
    return s[:show_chars] + "..." + s[-show_chars:]

def get_with_retry(url, **kwargs):
    last_error = None
    for attempt in range(RETRY_LIMIT):
        try:
            response = requests.get(url, **kwargs)
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as error:
            last_error = str(error)
        if attempt < RETRY_LIMIT - 1:
            time.sleep(2 ** attempt)
    logger.warning("GET failed after retries for %s: %s", url.split('?')[0], last_error)
    return None

def json_response(response):
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except (ValueError, requests.RequestException):
        return {}

def version_key(version):
    return tuple(int(part) for part in re.findall(r"\d+", str(version)))

def update_manifest():
    manifest_url = config.update_manifest_url or UPDATE_MANIFEST_URL
    if not manifest_url or not manifest_url.lower().startswith("https://"):
        return None
    try:
        response = requests.get(manifest_url, timeout=(3, 5))
        if response.status_code != 200:
            logger.warning("Update manifest returned HTTP %s", response.status_code)
            return None
        data = json_response(response)
        latest = data.get("version")
        download_url = data.get("download_url")
        checksum = data.get("sha256", "").lower()
        if not latest or not download_url or not checksum:
            logger.warning("Update manifest is missing required fields")
            return None
        if not str(download_url).lower().startswith("https://"):
            logger.warning("Refusing non-HTTPS update URL")
            return None
        return {
            "version": str(latest),
            "download_url": download_url,
            "sha256": checksum,
            "notes": str(data.get("notes", ""))
        }
    except (OSError, ValueError, TypeError, requests.RequestException) as error:
        logger.info("Update check skipped: %s", error)
        return None

def install_update(update):
    if not getattr(sys, "frozen", False):
        print("Updates are available only after building Spoofer.exe.")
        return False

    executable = os.path.abspath(sys.executable)
    temporary_path = executable + ".download"
    try:
        response = requests.get(update["download_url"], stream=True, timeout=(5, 120))
        response.raise_for_status()
        digest = hashlib.sha256()
        with open(temporary_path, "wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    digest.update(chunk)
                    output.write(chunk)
        if digest.hexdigest().lower() != update["sha256"]:
            raise ValueError("Downloaded update checksum does not match")

        updater_path = os.path.join(BASE_DIR, "apply_update.bat")
        old_path = executable + ".old"
        with open(updater_path, "w", encoding="utf-8", newline="\r\n") as updater:
            updater.write(
                "@echo off\r\n"
                "timeout /t 2 /nobreak >nul\r\n"
                f"move /y \"{executable}\" \"{old_path}\" >nul\r\n"
                f"move /y \"{temporary_path}\" \"{executable}\" >nul\r\n"
                f"start \"\" \"{executable}\"\r\n"
                f"del \"{old_path}\" >nul 2>&1\r\n"
                "del \"%~f0\" >nul 2>&1\r\n"
            )
        subprocess.Popen(["cmd", "/c", updater_path], creationflags=subprocess.CREATE_NO_WINDOW)
        print("Update downloaded. Restarting with the new version...")
        return True
    except (OSError, ValueError, requests.RequestException) as error:
        logger.error("Update failed: %s", error)
        print(f"Update failed: {error}")
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        return False

def check_for_updates():
    update = update_manifest()
    if not update or version_key(update["version"]) <= version_key(APP_VERSION):
        return False
    print(f"\nUpdate available: {APP_VERSION} -> {update['version']}")
    if update["notes"]:
        print(f"Notes: {update['notes']}")
    choice = input("Install this update now? [y/N]: ").strip().lower()
    if choice not in ("y", "yes"):
        return False
    return install_update(update)

def first_time_setup():
    print(f"\n{Fore.CYAN}=== MAIK'S SPOOFER SETUP ==={Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}[?] Get your .ROBLOSECURITY cookie:{Style.RESET_ALL}")
    print("   Roblox.com > F12 > Application > Cookies > .ROBLOSECURITY")
    cookie = input(f"\n{Fore.CYAN}[?] Cookie: {Style.RESET_ALL}").strip()
    if cookie:
        config.cookie = cookie
    
    print(f"\n{Fore.YELLOW}[?] Create API Key:{Style.RESET_ALL}")
    print("   https://create.roblox.com/dashboard/credentials")
    print("   USER key with assets.read + assets.write permissions")
    api_key = input(f"\n{Fore.CYAN}[?] API Key: {Style.RESET_ALL}").strip()
    if api_key:
        config.api_key = api_key
    
    print(f"\n{Fore.YELLOW}[?] Your Roblox User ID:{Style.RESET_ALL}")
    print("   Find in profile URL: roblox.com/users/YOUR_ID_HERE")
    user_id = input(f"\n{Fore.CYAN}[?] User ID: {Style.RESET_ALL}").strip()
    if user_id.isdigit():
        config.user_id = user_id
    
    config.save()
    print(f"\n{Fore.GREEN}[+] Setup complete!{Style.RESET_ALL}")
    input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")

def download_animation(anim_id):
    cookie = config.cookie
    headers = {
        'User-Agent': 'Roblox/WinInet',
        'Cookie': f'.ROBLOSECURITY={cookie}'
    }
    
    response = get_with_retry(
        f"https://assetdelivery.roblox.com/v1/asset/?id={anim_id}",
        headers=headers, timeout=DOWNLOAD_TIMEOUT
    )
    if response is not None and response.status_code == 200 and len(response.content) > 100:
        return response.content

    response = get_with_retry(
        f"https://assetdelivery.roblox.com/v1/asset?id={anim_id}",
        headers=headers, timeout=DOWNLOAD_TIMEOUT
    )
    if response is not None and response.status_code == 200:
        location = json_response(response).get('location', '')
        if location:
            asset_response = get_with_retry(location, timeout=DOWNLOAD_TIMEOUT)
            if asset_response is not None and asset_response.status_code == 200:
                if 100 < len(asset_response.content) <= MAX_ANIMATION_BYTES:
                    return asset_response.content

    logger.info("Could not download animation %s", anim_id)
    
    return None

def test_api_key():
    print(f"\n{Fore.YELLOW}[DEBUG] Testing API key...{Style.RESET_ALL}")
    
    try:
        payload = {
            'assetType': 'Animation',
            'displayName': f'Test_{int(time.time())}',
            'description': 'Test animation',
            'creationContext': {
                'creator': {
                    'userId': config.user_id
                }
            }
        }
        
        r = requests.post(
            "https://apis.roblox.com/assets/v1/assets",
            headers={
                'x-api-key': config.api_key,
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=UPLOAD_TIMEOUT
        )
        
        print(f"  HTTP Status: {r.status_code}")
        print(f"  Response: {r.text[:500]}")
        
        if r.status_code in [200, 201]:
            data = r.json()
            print(f"  {Fore.GREEN}[+] API KEY WORKS!{Style.RESET_ALL}")
            print(f"  Asset ID: {data.get('assetId')}")
            return True
        elif r.status_code == 401:
            print(f"  {Fore.RED}[!] Unauthorized - Key is invalid or expired{Style.RESET_ALL}")
        elif r.status_code == 403:
            print(f"  {Fore.RED}[!] Forbidden - Missing permissions (need assets.read + assets.write){Style.RESET_ALL}")
        elif r.status_code == 400:
            print(f"  {Fore.RED}[!] Bad Request - User ID might be wrong or payload invalid{Style.RESET_ALL}")
        return False
    except Exception as e:
        print(f"  {Fore.RED}[!] Error: {e}{Style.RESET_ALL}")
        return False

def upload_animation(animation_data, index=0):
    try:
        payload = {
            'assetType': 'Animation',
            'displayName': f'Anim_{int(time.time())}_{index}',
            'description': '',
            'creationContext': {
                'creator': {
                    'userId': config.user_id
                }
            }
        }
        
        r = requests.post(
            "https://apis.roblox.com/assets/v1/assets",
            headers={
                'x-api-key': config.api_key,
            },
            files={
                'request': (None, json.dumps(payload), 'application/json'),
                'fileContent': ('animation.rbxm', io.BytesIO(animation_data), 'application/octet-stream')
            },
            timeout=30
        )
        
        if r.status_code not in [200, 201, 202]:
            return None
        
        result = json_response(r)
        response = result.get('response') or {}
        asset_id = result.get('assetId') or result.get('id') or response.get('assetId')
        operation_path = result.get('path')

        if asset_id:
            return asset_id
        if not operation_path:
            return None

        operation_url = operation_path
        if not operation_url.startswith('http'):
            operation_url = f"https://apis.roblox.com/assets/v1/{operation_url.lstrip('/')}"

        deadline = time.monotonic() + OPERATION_TIMEOUT
        while time.monotonic() < deadline:
            operation_response = get_with_retry(
                operation_url,
                headers={'x-api-key': config.api_key},
                timeout=UPLOAD_TIMEOUT
            )
            if operation_response is None:
                continue
            operation = json_response(operation_response)
            if operation.get('done'):
                if operation.get('error'):
                    logger.warning("Roblox upload operation failed: %s", operation.get('error'))
                    return None
                operation_response = operation.get('response') or {}
                return operation_response.get('assetId') or operation_response.get('id')
            time.sleep(2)
        logger.warning("Roblox upload operation timed out")
        return None
    except (OSError, ValueError, TypeError, requests.RequestException) as error:
        logger.warning("Animation upload failed: %s", error)
        return None

@app.route('/status', methods=['GET'])
def status():
    with spoof_state_lock:
        busy = spoof_in_progress
    return jsonify({
        "status": "online",
        "version": APP_VERSION,
        "port": config.port,
        "busy": busy,
        "uptime": int(time.time() - START_TIME)
    })

@app.route('/spoof', methods=['POST'])
def spoof():
    data = request.get_json()
    if not data or 'anim_ids' not in data:
        return jsonify({"error": "No animation IDs supplied"}), 400
    
    raw_ids = data['anim_ids']
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"error": "Animation IDs must be a non-empty list"}), 400
    if len(raw_ids) > MAX_ANIMATIONS:
        return jsonify({"error": f"Too many animations (maximum {MAX_ANIMATIONS})"}), 413

    anim_ids = []
    for raw_id in raw_ids:
        try:
            anim_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if anim_id > 0 and anim_id not in anim_ids:
            anim_ids.append(anim_id)
    if not anim_ids:
        return jsonify({"error": "No valid animation IDs supplied"}), 400
    if not begin_spoof():
        return jsonify({"error": "A spoof operation is already running"}), 409
    total = len(anim_ids)
    
    print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[*] Processing {total} animations{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    if not config.cookie:
        end_spoof()
        return jsonify({"error": "Cookie not set"}), 401
    if not config.api_key:
        end_spoof()
        return jsonify({"error": "API key not set"}), 401
    if not config.user_id:
        end_spoof()
        return jsonify({"error": "User ID not set"}), 401
    
    # Phase 1: Download
    print(f"\n{Fore.YELLOW}[PHASE 1] Downloading...{Style.RESET_ALL}")
    downloaded = {}
    lock = threading.Lock()
    done = [0]
    ok = [0]
    
    def dl_worker(aid):
        r = download_animation(aid)
        with lock:
            done[0] += 1
            if r:
                ok[0] += 1
                downloaded[str(aid)] = r
            if done[0] % 20 == 0:
                print(f"  [{done[0]}/{total}] {ok[0]} downloaded")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        list(ex.map(dl_worker, anim_ids))
    
    print(f"\n{Fore.CYAN}[*] Downloaded: {Fore.GREEN}{len(downloaded)}{Fore.CYAN}/{total}{Style.RESET_ALL}")
    
    if not downloaded:
        end_spoof()
        return jsonify({"error": "No animations could be downloaded"}), 500
    
    # Phase 2: Upload
    print(f"\n{Fore.YELLOW}[PHASE 2] Uploading...{Style.RESET_ALL}")
    mapping = {}
    total_up = len(downloaded)
    done_up = [0]
    ok_up = [0]
    lock_up = threading.Lock()
    
    def ul_worker(indexed_item):
        upload_index, item = indexed_item
        oid, adat = item
        nid = upload_animation(adat, upload_index)
        with lock_up:
            done_up[0] += 1
            if nid:
                ok_up[0] += 1
                mapping[oid] = str(nid)
            if done_up[0] % 5 == 0:
                print(f"  [{done_up[0]}/{total_up}] {ok_up[0]} uploaded")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(ul_worker, enumerate(downloaded.items())))
    
    print(f"\n{Fore.CYAN}[*] Uploaded: {Fore.GREEN}{len(mapping)}{Fore.CYAN}/{total_up}{Style.RESET_ALL}")
    
    if mapping:
        print(f"\n{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] SPOOFED: {len(mapping)}/{total}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*50}{Style.RESET_ALL}")
        end_spoof()
        return jsonify(mapping)
    else:
        end_spoof()
        return jsonify({"error": "Uploads failed - check API key permissions"}), 500

def run_flask():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    app.run(host='127.0.0.1', port=config.port, debug=False, use_reloader=False)

def start_server():
    global server_thread, server_running
    if server_running:
        print(f"{Fore.YELLOW}[!] Already running!{Style.RESET_ALL}")
        return
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', config.port))
    except OSError:
        print(f"{Fore.RED}[!] Port {config.port} is already in use.{Style.RESET_ALL}")
        logger.error("Could not start server: port %s is unavailable", config.port)
        return
    print(f"\n{Fore.GREEN}[*] Server: http://localhost:{config.port}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[*] Waiting for Studio...{Style.RESET_ALL}\n")
    server_thread = threading.Thread(target=run_flask, daemon=True)
    server_thread.start()
    server_running = True
    logger.info("Local server started on port %s", config.port)

PLUGIN_LUA_CODE = '''-- Maik's Spoofer Plugin
-- Place in Roblox Plugins folder

local HttpService = game:GetService("HttpService")
local StarterGui = game:GetService("StarterGui")
local port = 5555
local baseUrl = "http://localhost:"

local toolbar = plugin:CreateToolbar("Maik")
local btn = toolbar:CreateButton("Spoofer", "Animation Spoofer", "")

local wi = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Float, false, false, 280, 260, 260, 240)
local gui = plugin:CreateDockWidgetPluginGui("MaikGUI", wi)
gui.Title = "Maik's Spoofer"

local m = Instance.new("Frame")
m.Size = UDim2.new(1, 0, 1, 0)
m.BackgroundColor3 = Color3.fromRGB(22, 22, 22)
m.BorderSizePixel = 0
m.Parent = gui

local h = Instance.new("Frame")
h.Size = UDim2.new(1, 0, 0, 34)
h.BackgroundColor3 = Color3.fromRGB(30, 30, 30)
h.BorderSizePixel = 0
h.Parent = m

local t = Instance.new("TextLabel")
t.Text = "MAIK'S SPOOFER"
t.Size = UDim2.new(1, 0, 1, 0)
t.TextColor3 = Color3.fromRGB(255, 255, 255)
t.BackgroundTransparency = 1
t.TextSize = 14
t.Font = Enum.Font.GothamBold
t.Parent = h

local c = Instance.new("Frame")
c.Size = UDim2.new(1, -30, 1, -46)
c.Position = UDim2.new(0, 15, 0, 44)
c.BackgroundTransparency = 1
c.Parent = m

local pl = Instance.new("TextLabel")
pl.Text = "PORT"
pl.Size = UDim2.new(0, 32, 0, 20)
pl.TextColor3 = Color3.fromRGB(140, 140, 140)
pl.BackgroundTransparency = 1
pl.TextSize = 9
pl.Font = Enum.Font.GothamBold
pl.TextXAlignment = Enum.TextXAlignment.Left
pl.Parent = c

local pb = Instance.new("TextBox")
pb.Text = "5555"
pb.Size = UDim2.new(0, 60, 0, 20)
pb.Position = UDim2.new(0, 36, 0, 0)
pb.BackgroundColor3 = Color3.fromRGB(38, 38, 38)
pb.TextColor3 = Color3.fromRGB(255, 255, 255)
pb.BorderSizePixel = 0
pb.TextSize = 10
pb.Parent = c

local cn = Instance.new("TextButton")
cn.Text = "CONNECT"
cn.Size = UDim2.new(1, 0, 0, 28)
cn.Position = UDim2.new(0, 0, 0, 30)
cn.BackgroundColor3 = Color3.fromRGB(0, 105, 200)
cn.TextColor3 = Color3.fromRGB(255, 255, 255)
cn.BorderSizePixel = 0
cn.TextSize = 11
cn.Font = Enum.Font.GothamBold
cn.Parent = c

local sp = Instance.new("TextButton")
sp.Text = "SPOOF"
sp.Size = UDim2.new(1, 0, 0, 28)
sp.Position = UDim2.new(0, 0, 0, 64)
sp.BackgroundColor3 = Color3.fromRGB(0, 145, 0)
sp.TextColor3 = Color3.fromRGB(255, 255, 255)
sp.BorderSizePixel = 0
sp.TextSize = 11
sp.Font = Enum.Font.GothamBold
sp.Parent = c

local st = Instance.new("Frame")
st.Size = UDim2.new(1, 0, 0, 20)
st.Position = UDim2.new(0, 0, 0, 102)
st.BackgroundColor3 = Color3.fromRGB(32, 32, 32)
st.BorderSizePixel = 0
st.Parent = c

local sl = Instance.new("TextLabel")
sl.Text = "READY"
sl.Size = UDim2.new(1, -8, 1, 0)
sl.Position = UDim2.new(0, 5, 0, 0)
sl.TextColor3 = Color3.fromRGB(150, 150, 150)
sl.BackgroundTransparency = 1
sl.TextSize = 9
sl.Font = Enum.Font.GothamBold
sl.TextXAlignment = Enum.TextXAlignment.Left
sl.Parent = st

local pf = Instance.new("Frame")
pf.Size = UDim2.new(1, 0, 0, 2)
pf.Position = UDim2.new(0, 0, 0, 128)
pf.BackgroundColor3 = Color3.fromRGB(45, 45, 45)
pf.BorderSizePixel = 0
pf.Visible = false
pf.Parent = c

local pb2 = Instance.new("Frame")
pb2.Size = UDim2.new(0, 0, 1, 0)
pb2.BackgroundColor3 = Color3.fromRGB(0, 200, 100)
pb2.BorderSizePixel = 0
pb2.Parent = pf

local ll = Instance.new("TextLabel")
ll.Text = ""
ll.Size = UDim2.new(1, 0, 0, 40)
ll.Position = UDim2.new(0, 0, 0, 135)
ll.TextColor3 = Color3.fromRGB(120, 120, 120)
ll.BackgroundTransparency = 1
ll.TextSize = 9
ll.TextXAlignment = Enum.TextXAlignment.Left
ll.TextYAlignment = Enum.TextYAlignment.Top
ll.TextWrapped = true
ll.Parent = c

local function up()
    local p = tonumber(pb.Text)
    if p then port = p end
end

pb.FocusLost:Connect(up)

cn.MouseButton1Click:Connect(function()
    up()
    sl.Text = "CONNECTING..."
    sl.TextColor3 = Color3.fromRGB(255, 170, 0)
    local ok, res = pcall(function()
        return HttpService:GetAsync(baseUrl .. port .. "/status")
    end)
    if ok then
        local data = HttpService:JSONDecode(res)
        if data.status == "online" then
            sl.Text = "CONNECTED"
            sl.TextColor3 = Color3.fromRGB(0, 255, 120)
            ll.Text = "Ready to spoof!"
        end
    else
        sl.Text = "OFFLINE"
        sl.TextColor3 = Color3.fromRGB(255, 60, 60)
        ll.Text = "Start Maik's Spoofer first!"
    end
end)

sp.MouseButton1Click:Connect(function()
    up()
    sl.Text = "SCANNING..."
    sl.TextColor3 = Color3.fromRGB(255, 170, 0)
    pf.Visible = true
    pb2.Size = UDim2.new(0.1, 0, 1, 0)
    
    local ids = {}
    local anms = {}
    
    local function sc(x)
        if not x then return end
        pcall(function()
            for _, o in ipairs(x:GetDescendants()) do
                if o:IsA("Animation") then
                    local n = string.match(o.AnimationId, "%d+")
                    if n and tonumber(n) > 0 then
                        table.insert(anms, o)
                        if not table.find(ids, tonumber(n)) then
                            table.insert(ids, tonumber(n))
                        end
                    end
                end
            end
        end)
    end
    
    sc(game:GetService("Workspace"))
    sc(game:GetService("ReplicatedStorage"))
    sc(game:GetService("ServerStorage"))
    sc(game:GetService("StarterPlayer"))
    sc(game:GetService("ServerScriptService"))
    sc(game:GetService("Lighting"))
    
    pb2.Size = UDim2.new(0.3, 0, 1, 0)
    
    if #ids == 0 then
        sl.Text = "NONE FOUND"
        sl.TextColor3 = Color3.fromRGB(255, 130, 0)
        ll.Text = "No animations in this game!"
        pf.Visible = false
        return
    end
    
    ll.Text = "Found " .. #ids .. " animations..."
    sl.Text = "SPOOFING..."
    sl.TextColor3 = Color3.fromRGB(0, 170, 255)
    pb2.Size = UDim2.new(0.5, 0, 1, 0)
    
    local ok, res = pcall(function()
        return HttpService:PostAsync(
            baseUrl .. port .. "/spoof",
            HttpService:JSONEncode({anim_ids = ids}),
            Enum.HttpContentType.ApplicationJson
        )
    end)
    
    if ok then
        local d = HttpService:JSONDecode(res)
        
        if d.error then
            sl.Text = "ERROR"
            sl.TextColor3 = Color3.fromRGB(255, 60, 60)
            ll.Text = d.error
            pf.Visible = false
            return
        end
        
        pb2.Size = UDim2.new(0.8, 0, 1, 0)
        local rp = 0
        
        for _, a in ipairs(anms) do
            local o = string.match(a.AnimationId, "%d+")
            if o and d[o] then
                a.AnimationId = "rbxassetid://" .. d[o]
                rp = rp + 1
            end
        end
        
        pb2.Size = UDim2.new(1, 0, 1, 0)
        sl.Text = "DONE"
        sl.TextColor3 = Color3.fromRGB(0, 255, 120)
        ll.Text = "Spoofed " .. rp .. "/" .. #ids .. "!"
        
        StarterGui:SetCore("SendNotification", {
            Title = "Maik's Spoofer",
            Text = "Spoofed " .. rp .. " animations!",
            Duration = 4
        })
    else
        sl.Text = "ERROR"
        sl.TextColor3 = Color3.fromRGB(255, 60, 60)
        ll.Text = tostring(res)
    end
    
    pf.Visible = false
end)

btn.Click:Connect(function()
    gui.Enabled = not gui.Enabled
end)
'''

def generate_plugin():
    print(f"\n{Fore.CYAN}[*] Generating plugin...{Style.RESET_ALL}")
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Maiks_Spoofer_Plugin.lua")
    target = os.path.abspath("Maiks_Spoofer_Plugin.lua")
    if not os.path.exists(source):
        raise FileNotFoundError(f"Plugin source not found: {source}")
    with open(source, "r", encoding="utf-8") as source_file:
        plugin_code = source_file.read()
    with open(target, "w", encoding="utf-8") as target_file:
        target_file.write(plugin_code)
    print(f"{Fore.GREEN}[+] Saved: Maiks_Spoofer_Plugin.lua{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Install:{Style.RESET_ALL} Put in Roblox Plugins folder & restart Studio")

def settings_menu():
    while True:
        print(f"\n{Fore.CYAN}=== SETTINGS ==={Style.RESET_ALL}\n")
        print(f"Port: {config.port}")
        print(f"User ID: {config.user_id or 'NOT SET'}")
        print(f"Cookie: {mask_string(config.cookie)}")
        print(f"API Key: {mask_string(config.api_key)}")
        print(f"Updates: {'CONFIGURED' if config.update_manifest_url else 'OFF'}")
        print(f"\n[1] Change Port")
        print(f"[2] Change User ID")
        print(f"[3] Change Cookie")
        print(f"[4] Change API Key")
        print(f"[5] Set Update URL")
        print(f"[6] Reset All Settings")
        print(f"[7] Back")
        
        choice = input(f"\n{Fore.CYAN}[?] Select: {Style.RESET_ALL}").strip()
        
        if choice == "1":
            p = input("New port: ").strip()
            if p.isdigit() and 1 <= int(p) <= 65535:
                config.port = int(p)
                config.save()
                print(f"{Fore.GREEN}[+] Updated{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}[!] Port must be between 1 and 65535{Style.RESET_ALL}")
        
        elif choice == "2":
            u = input("New User ID: ").strip()
            if u.isdigit():
                config.user_id = u
                config.save()
                print(f"{Fore.GREEN}[+] Updated{Style.RESET_ALL}")
        
        elif choice == "3":
            ck = input("New Cookie: ").strip()
            if ck:
                config.cookie = ck
                config.save()
                print(f"{Fore.GREEN}[+] Updated{Style.RESET_ALL}")
        
        elif choice == "4":
            k = input("New API Key: ").strip()
            if k:
                config.api_key = k
                config.save()
                print(f"{Fore.GREEN}[+] Updated{Style.RESET_ALL}")
        
        elif choice == "5":
            update_url = input("HTTPS update manifest URL (blank disables): ").strip()
            if not update_url or update_url.lower().startswith("https://"):
                config.update_manifest_url = update_url
                config.save()
                print(f"{Fore.GREEN}[+] Update source saved{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}[!] Update URL must use HTTPS{Style.RESET_ALL}")

        elif choice == "6":
            confirm = input(f"{Fore.RED}[!] Delete all settings? (y/n): {Style.RESET_ALL}").strip().lower()
            if confirm == 'y':
                if os.path.exists(CONFIG_FILE):
                    os.remove(CONFIG_FILE)
                config.cookie = ""
                config.api_key = ""
                config.user_id = ""
                config.port = DEFAULT_PORT
                config.update_manifest_url = ""
                print(f"{Fore.GREEN}[+] Settings reset. Restart the program.{Style.RESET_ALL}")
                sys.exit(0)
        
        elif choice == "7":
            break

def main_menu():
    while True:
        print(f"\n{Fore.CYAN}Maik's Spoofer{Style.RESET_ALL}")
        
        if config.cookie:
            cs = "OK"
        else:
            cs = "NOT SET"
        
        if config.api_key:
            aps = "OK"
        else:
            aps = "NOT SET"
        
        if config.user_id:
            us = config.user_id
        else:
            us = "NOT SET"
        
        if server_running:
            ss = "ONLINE"
        else:
            ss = "OFFLINE"
        
        print(f"Port      {config.port}")
        print(f"User      {us}")
        print(f"Cookie    {cs}")
        print(f"API key   {aps}")
        print(f"Server    {ss}")
        print("\n1. Start server")
        print("2. Generate plugin")
        print("3. Settings")
        print("4. Exit")
        
        choice = input(f"\n{Fore.CYAN}[?] Select: {Style.RESET_ALL}").strip()
        
        if choice == "1":
            start_server()
            input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        
        elif choice == "2":
            generate_plugin()
            input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        
        elif choice == "3":
            settings_menu()
        
        elif choice == "4":
            print(f"\n{Fore.YELLOW}[*] Exiting Maik's Spoofer...{Style.RESET_ALL}")
            sys.exit(0)

if __name__ == "__main__":
    try:
        if config.is_first_run():
            first_time_setup()
        check_for_updates()
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}[*] Exiting Maik's Spoofer...{Style.RESET_ALL}")
        sys.exit(0)