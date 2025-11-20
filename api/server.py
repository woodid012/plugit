"""
Smart Home Control Server
Flask backend for controlling Tapo, Meross, Arlec, and Matter devices
Updated for Vercel deployment compatibility
"""

import sys
from pathlib import Path

# Add project root to Python path for imports (needed since server.py is in api/)
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import asyncio
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import os
import json
from datetime import datetime, timedelta
import time

# Import credentials - with fallback to environment variables for Vercel
# Use a function to delay import until runtime
def _load_ios_logins():
    """Load credentials from IoS_logins.py or environment variables"""
    try:
        import importlib
        _ios_logins_module = importlib.import_module('IoS_logins')
        return {
            'TAPO_EMAIL': _ios_logins_module.TAPO_EMAIL,
            'TAPO_PASSWORD': _ios_logins_module.TAPO_PASSWORD,
            'MEROSS_EMAIL': _ios_logins_module.MEROSS_EMAIL,
            'MEROSS_PASSWORD': _ios_logins_module.MEROSS_PASSWORD,
            'TUYA_ACCESS_ID': _ios_logins_module.TUYA_ACCESS_ID,
            'TUYA_ACCESS_SECRET': _ios_logins_module.TUYA_ACCESS_SECRET,
            'TUYA_API_REGION': _ios_logins_module.TUYA_API_REGION,
            'KNOWN_DEVICES': _ios_logins_module.KNOWN_DEVICES,
            'MATTER_DEVICES': _ios_logins_module.MATTER_DEVICES,
            'get_all_matter_devices': _ios_logins_module.get_all_matter_devices,
            'MONGO_USERNAME': _ios_logins_module.MONGO_USERNAME,
            'MONGO_PASSWORD': _ios_logins_module.MONGO_PASSWORD,
            'MONGO_URI': _ios_logins_module.MONGO_URI,
            'MONGO_DB_NAME': _ios_logins_module.MONGO_DB_NAME,
            'MONGO_COLLECTION_NAME': _ios_logins_module.MONGO_COLLECTION_NAME,
        }
    except (ImportError, ModuleNotFoundError) as e:
        print(f"[INFO] IoS_logins.py not found ({e}), using environment variables")
        return None

# Try to load from IoS_logins.py
_creds = _load_ios_logins()
if _creds:
    TAPO_EMAIL = _creds['TAPO_EMAIL']
    TAPO_PASSWORD = _creds['TAPO_PASSWORD']
    MEROSS_EMAIL = _creds['MEROSS_EMAIL']
    MEROSS_PASSWORD = _creds['MEROSS_PASSWORD']
    TUYA_ACCESS_ID = _creds['TUYA_ACCESS_ID']
    TUYA_ACCESS_SECRET = _creds['TUYA_ACCESS_SECRET']
    TUYA_API_REGION = _creds['TUYA_API_REGION']
    KNOWN_DEVICES = _creds['KNOWN_DEVICES']
    MATTER_DEVICES = _creds['MATTER_DEVICES']
    get_all_matter_devices = _creds['get_all_matter_devices']
    MONGO_USERNAME = _creds['MONGO_USERNAME']
    MONGO_PASSWORD = _creds['MONGO_PASSWORD']
    MONGO_URI = _creds['MONGO_URI']
    MONGO_DB_NAME = _creds['MONGO_DB_NAME']
    MONGO_COLLECTION_NAME = _creds['MONGO_COLLECTION_NAME']
    _has_ios_logins = True
else:
    _has_ios_logins = False

if not _has_ios_logins:
    # Fallback to environment variables (for Vercel deployment)
    print("[INFO] IoS_logins.py not found, using environment variables")
    TAPO_EMAIL = os.getenv('TAPO_EMAIL', '')
    TAPO_PASSWORD = os.getenv('TAPO_PASSWORD', '')
    MEROSS_EMAIL = os.getenv('MEROSS_EMAIL', '')
    MEROSS_PASSWORD = os.getenv('MEROSS_PASSWORD', '')
    TUYA_ACCESS_ID = os.getenv('TUYA_ACCESS_ID', '')
    TUYA_ACCESS_SECRET = os.getenv('TUYA_ACCESS_SECRET', '')
    TUYA_API_REGION = os.getenv('TUYA_API_REGION', 'us')
    
    # Parse JSON strings for complex data structures
    KNOWN_DEVICES = {}
    MATTER_DEVICES = {}
    try:
        known_devices_str = os.getenv('KNOWN_DEVICES', '{}')
        if known_devices_str:
            KNOWN_DEVICES = json.loads(known_devices_str)
    except:
        KNOWN_DEVICES = {}
    
    try:
        matter_devices_str = os.getenv('MATTER_DEVICES', '{}')
        if matter_devices_str:
            MATTER_DEVICES = json.loads(matter_devices_str)
    except:
        MATTER_DEVICES = {}
    
    def get_all_matter_devices():
        """Fallback function for get_all_matter_devices"""
        devices = []
        for device_id, device_info in MATTER_DEVICES.items():
            devices.append({
                'device_id': device_id,
                'ip': device_info.get('ip'),
                'port': device_info.get('port', 5540),
                'name': device_info.get('name', device_id)
            })
        return devices
    
    MONGO_USERNAME = os.getenv('MONGO_USERNAME', '')
    MONGO_PASSWORD = os.getenv('MONGO_PASSWORD', '')
    MONGO_URI = os.getenv('MONGO_URI', '')
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', '')
    MONGO_COLLECTION_NAME = os.getenv('MONGO_COLLECTION_NAME', '')

# Import device libraries
from tapo import ApiClient
from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager
import tinytuya

# Import Matter controller
try:
    from Matter.matter_controller import MatterController
    MATTER_AVAILABLE = True
except ImportError:
    MATTER_AVAILABLE = False
    print("[WARNING] Matter controller not available. Install Matter dependencies.")

# Import data collection module
try:
    from data_collection.device_usage_collector import collect_and_save, connect_mongo
    DATA_COLLECTION_AVAILABLE = True
except ImportError:
    DATA_COLLECTION_AVAILABLE = False
    print("[WARNING] Data collection module not available.")

app = Flask(__name__)
CORS(app)

# Server start timestamp (used to detect restarts and clear browser cache)
SERVER_START_TIME = time.time()

# Global variables for Meross
meross_manager = None
meross_http_client = None
meross_devices = []
meross_loop = None
meross_loop_thread = None

# Global variables for Arlec (Tuya Cloud)
arlec_cloud = None
arlec_devices = []
arlec_devices_list = []  # List of Arlec device IDs for timeseries collection

# Global variables for Matter devices
matter_devices_list = []  # List of {device_id, ip, name, port} for timeseries collection

# Global variables for Tapo devices (for timeseries collection)
tapo_devices_list = []  # List of {device_id, ip, email, password, name}

# Dynamic Tapo device storage (device_id -> {ip, email, password})
# This allows adding devices without modifying IoS_logins.py
tapo_devices_storage = {}
TAPO_DEVICES_FILE = Path(__file__).parent.parent / 'tapo_devices.json'

# Timeseries data is now stored in browser localStorage (client-side only)

# Windows event loop policy
if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def run_in_meross_loop(coro):
    """Run a coroutine in the Meross event loop thread"""
    global meross_loop
    if meross_loop is None:
        raise RuntimeError("Meross loop not initialized")

    future = asyncio.run_coroutine_threadsafe(coro, meross_loop)
    return future.result(timeout=30)  # 30 second timeout


def load_tapo_devices():
    """Load dynamically added Tapo devices from file"""
    global tapo_devices_storage
    
    if not TAPO_DEVICES_FILE.exists():
        return
    
    try:
        with TAPO_DEVICES_FILE.open('r') as f:
            tapo_devices_storage = json.load(f)
        
        if tapo_devices_storage:
            print(f"[OK] Loaded {len(tapo_devices_storage)} dynamically added Tapo device(s) from {TAPO_DEVICES_FILE}")
    except Exception as e:
        print(f"[ERROR] Failed to load Tapo devices: {e}")
        tapo_devices_storage = {}


def save_tapo_devices():
    """Save dynamically added Tapo devices to file"""
    global tapo_devices_storage
    
    try:
        with TAPO_DEVICES_FILE.open('w') as f:
            json.dump(tapo_devices_storage, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save Tapo devices: {e}")


def init_arlec():
    """Initialize Arlec (Tuya Cloud) connection"""
    global arlec_cloud, arlec_devices

    try:
        arlec_cloud = tinytuya.Cloud(
            apiRegion=TUYA_API_REGION,
            apiKey=TUYA_ACCESS_ID,
            apiSecret=TUYA_ACCESS_SECRET
        )

        # Discover devices
        arlec_devices = arlec_cloud.getdevices()
        
        if arlec_devices:
            print(f"[OK] Arlec: Found {len(arlec_devices)} device(s)")
        else:
            print("[WARNING] Arlec: No devices found")
            arlec_devices = []
    except Exception as e:
        print(f"[ERROR] Arlec initialization error: {e}")
        arlec_devices = []


async def init_meross():
    """Initialize Meross connection"""
    global meross_manager, meross_http_client, meross_devices

    try:
        # Use AP (Asia-Pacific) server to avoid redirect
        meross_http_client = await MerossHttpClient.async_from_user_password(
            api_base_url="https://iotx-ap.meross.com",
            email=MEROSS_EMAIL,
            password=MEROSS_PASSWORD
        )

        meross_manager = MerossManager(http_client=meross_http_client)
        await meross_manager.async_init()
        await meross_manager.async_device_discovery()
        meross_devices = meross_manager.find_devices()

        print(f"[OK] Meross: Found {len(meross_devices)} devices")
    except Exception as e:
        print(f"[ERROR] Meross initialization error: {e}")


async def get_tapo_device(ip, email=None, password=None):
    """Get a Tapo device connection - supports P100, P110, and other models"""
    try:
        # Use provided credentials or fall back to defaults
        tapo_email = email or TAPO_EMAIL
        tapo_password = password or TAPO_PASSWORD
        client = ApiClient(tapo_email, tapo_password)
        
        # Try P110 first (newer model), then fall back to P100
        # The p100() method often works for P110 too, but try p110 if available
        # Reduced timeout from 3.0s to 1.5s for faster loading
        try:
            if hasattr(client, 'p110'):
                device = await asyncio.wait_for(client.p110(ip), timeout=1.5)
            else:
                # Fall back to p100 (works for most Tapo smart plugs)
                device = await asyncio.wait_for(client.p100(ip), timeout=1.5)
        except AttributeError:
            # If p110 doesn't exist, use p100
            device = await asyncio.wait_for(client.p100(ip), timeout=1.5)
        
        return device
    except asyncio.TimeoutError:
        return None  # Timeout - device unreachable, fail silently for speed
    except Exception as e:
        return None  # Connection error - fail silently for speed


async def get_tapo_status(ip, email=None, password=None, device_name=None):
    """Get Tapo device status"""
    try:
        device = await get_tapo_device(ip, email, password)
        if device:
            info = await device.get_device_info()
            # Use provided name or extract from device nickname/model
            name = device_name or 'Smart Plug'
            if hasattr(info, 'nickname') and info.nickname:
                name = info.nickname
            elif device_name:
                # Convert device_id to readable name (e.g., "tapo_wine_fridge_monitor" -> "Wine Fridge")
                name = device_name.replace('tapo_', '').replace('_', ' ').title()
                # Remove "Monitor" suffix if present for cleaner display
                if name.endswith(' Monitor'):
                    name = name[:-8]
            
            # Use model from device info to auto-populate type
            # Format: "P110" or "P100" etc. (without "Tapo" prefix)
            device_type = info.model if info.model else 'Smart Plug'
            
            device_status = {
                'name': name,
                'type': device_type,
                'ip': ip,
                'status': 'on' if info.device_on else 'off',
                'online': True,
                'model': info.model,
                'rssi': info.rssi
            }
            
            # Try to get current power data (power monitoring) - with timeout for faster loading
            try:
                # Use asyncio.wait_for to timeout power call (don't block on slow devices)
                current_power = await asyncio.wait_for(device.get_current_power(), timeout=2.0)
                if current_power and hasattr(current_power, 'current_power'):
                    power_watts = current_power.current_power
                    if power_watts is not None:
                        # Convert to float and ensure it's a number
                        power_watts = float(power_watts)
                        device_status['power'] = round(power_watts, 2)

                        # Calculate current (Amps) assuming 240V (Australian standard)
                        # Power (W) = Voltage (V) × Current (A)
                        # Current (A) = Power (W) / Voltage (V)
                        voltage = 240.0  # Standard voltage in Australia
                        current_amps = power_watts / voltage
                        device_status['current'] = round(current_amps, 2)
                        device_status['voltage'] = round(voltage, 1)
            except asyncio.TimeoutError:
                # Power call timed out - skip it for faster loading, device still works
                pass
            except Exception as e:
                # Energy monitoring not available or failed - device still works
                pass  # Silently skip on initial load for speed
            
            return device_status
    except Exception as e:
        print(f"Error getting Tapo status for {ip}: {e}")
        import traceback
        traceback.print_exc()

    # Return offline device with proper name
    name = device_name or 'Smart Plug'
    if device_name and not name.startswith('Smart'):
        # Convert device_id to readable name
        name = device_name.replace('tapo_', '').replace('_', ' ').title()
        # Remove "Monitor" suffix if present for cleaner display
        if name.endswith(' Monitor'):
            name = name[:-8]
    
    return {
        'name': name,
        'type': 'Smart Plug',  # Default when offline (model unknown)
        'ip': ip,
        'status': 'unknown',
        'online': False
    }


async def control_tapo(ip, action, email=None, password=None):
    """Control a Tapo device"""
    try:
        device = await get_tapo_device(ip, email, password)
        if not device:
            return {'success': False, 'error': 'Could not connect to device'}

        if action == 'on':
            await device.on()
        elif action == 'off':
            await device.off()
        else:
            return {'success': False, 'error': 'Invalid action'}

        return {'success': True, 'action': action}
    except Exception as e:
        return {'success': False, 'error': str(e)}


async def get_meross_status_async():
    """Get all Meross devices status (async)"""
    global meross_devices

    devices_status = []

    try:
        for device in meross_devices:
            try:
                # Update device status
                await device.async_update()

                # Build device status - access state right after update in same async context
                device_info = {
                    'name': device.name,
                    'type': device.type,
                    'uuid': device.uuid,
                    'status': 'on' if device.is_on() else 'off',
                    'online': device.online_status.name == 'ONLINE'
                }

                # Try to get energy monitoring data if available
                try:
                    # MSS310 devices use async_get_instant_metrics()
                    if hasattr(device, 'async_get_instant_metrics'):
                        metrics = await device.async_get_instant_metrics()
                        # metrics is an InstantElectricityMeasurement object
                        if metrics:
                            device_info['power'] = metrics.power  # Already in Watts
                            device_info['current'] = metrics.current  # Already in Amps
                            device_info['voltage'] = metrics.voltage  # Already in Volts
                except Exception as e:
                    print(f"Could not get electricity data for {device.name}: {e}")

                devices_status.append(device_info)
            except Exception as e:
                print(f"Error updating device {device.name}: {e}")
                # Add device with unknown status
                devices_status.append({
                    'name': device.name,
                    'type': device.type,
                    'uuid': device.uuid,
                    'status': 'unknown',
                    'online': False
                })
    except Exception as e:
        print(f"Error getting Meross status: {e}")

    return devices_status


def get_arlec_status():
    """Get all Arlec devices status - matches Meross format"""
    global arlec_devices, arlec_cloud
    
    devices_status = []
    
    if not arlec_cloud or not arlec_devices:
        return devices_status
    
    try:
        for device in arlec_devices:
            try:
                device_id = device.get('id')
                if not device_id:
                    continue
                
                # Get device status
                status = arlec_cloud.getstatus(device_id)
                
                # Extract switch state and energy data
                switch_state = False
                power = None
                voltage = None
                current = None
                
                if status and 'result' in status:
                    for item in status['result']:
                        code = item.get('code', '')
                        value = item.get('value')
                        
                        if code == 'switch_1':
                            switch_state = bool(value) if value is not None else False
                        elif code == 'cur_power':
                            # Power: value is in 0.1W units, convert to W
                            if value is not None:
                                power = float(value) / 10.0
                        elif code == 'cur_voltage':
                            # Voltage: value is in 0.1V units, convert to V
                            if value is not None:
                                voltage = float(value) / 10.0
                        elif code == 'cur_current':
                            # Current: value is in mA, convert to A
                            if value is not None:
                                current = float(value) / 1000.0
                
                # Determine online status - device is online if we can get status
                is_online = status is not None and status.get('success', False)
                if not is_online:
                    # Fall back to device online field
                    is_online = device.get('online', False) is True
                
                # Build device info matching Meross format
                device_info = {
                    'name': device.get('name', 'Arlec Device'),
                    'type': device.get('product_name', 'Arlec Smart Plug'),
                    'uuid': device_id,  # Use 'uuid' to match Meross format
                    'status': 'on' if switch_state else 'off',
                    'online': is_online
                }
                
                # Add energy data if available (same format as Meross)
                if power is not None:
                    device_info['power'] = round(power, 2)
                if voltage is not None:
                    device_info['voltage'] = round(voltage, 1)
                if current is not None:
                    device_info['current'] = round(current, 2)
                
                devices_status.append(device_info)
            except Exception as e:
                print(f"Error getting Arlec device status {device.get('name', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                # Add device with unknown status (matching Meross format)
                devices_status.append({
                    'name': device.get('name', 'Arlec Device'),
                    'type': device.get('product_name', 'Arlec Smart Plug'),
                    'uuid': device.get('id', 'unknown'),
                    'status': 'unknown',
                    'online': False
                })
    except Exception as e:
        print(f"Error getting Arlec status: {e}")
        import traceback
        traceback.print_exc()
    
    return devices_status


def control_arlec(device_id, action):
    """Control an Arlec device"""
    global arlec_cloud
    
    if not arlec_cloud:
        return {'success': False, 'error': 'Arlec cloud not initialized'}
    
    try:
        if action == 'on':
            result = arlec_cloud.sendcommand(
                device_id,
                {'commands': [{'code': 'switch_1', 'value': True}]}
            )
        elif action == 'off':
            result = arlec_cloud.sendcommand(
                device_id,
                {'commands': [{'code': 'switch_1', 'value': False}]}
            )
        elif action == 'toggle':
            # Get current status first
            status = arlec_cloud.getstatus(device_id)
            current_state = False
            
            if status and 'result' in status:
                for item in status['result']:
                    if item.get('code') == 'switch_1':
                        current_state = bool(item.get('value', False))
                        break
            
            # Toggle
            new_value = not current_state
            result = arlec_cloud.sendcommand(
                device_id,
                {'commands': [{'code': 'switch_1', 'value': new_value}]}
            )
        else:
            return {'success': False, 'error': 'Invalid action'}
        
        if result.get('success', False):
            return {
                'success': True,
                'action': action
            }
        else:
            return {'success': False, 'error': str(result)}
    except Exception as e:
        print(f"Error controlling Arlec device: {e}")
        return {'success': False, 'error': str(e)}


async def get_matter_status(device_id, ip=None, port=5540, device_name=None):
    """Get Matter device status"""
    if not MATTER_AVAILABLE:
        return {
            'name': device_name or 'Matter Device',
            'type': 'Smart Plug',
            'status': 'unknown',
            'online': False,
            'error': 'Matter library not available'
        }
    
    try:
        controller = MatterController(device_id, ip, port)
        
        # Try to connect and get status
        status = await controller.get_status()
        
        if status.get('online'):
            # Get device info
            info = await controller.get_info()
            
            # Try to get energy data
            energy_data = await controller.get_energy_usage()
            
            device_status = {
                'name': device_name or 'Matter Device',
                'type': 'Smart Plug',
                'status': status.get('status', 'unknown'),
                'online': True,
                'uuid': device_id,  # Use device_id as UUID for consistency
                'id': device_id
            }
            
            # Add energy data if available
            if energy_data:
                if energy_data.get('power') is not None:
                    device_status['power'] = round(energy_data['power'], 2)
                if energy_data.get('voltage') is not None:
                    device_status['voltage'] = round(energy_data['voltage'], 1)
                if energy_data.get('current') is not None:
                    device_status['current'] = round(energy_data['current'], 2)
            
            # Add device info if available
            if info:
                if hasattr(info, 'product_name'):
                    device_status['type'] = info.product_name
                if hasattr(info, 'vendor_name'):
                    device_status['vendor'] = info.vendor_name
            
            controller.disconnect()
            return device_status
        else:
            controller.disconnect()
            return {
                'name': device_name or 'Matter Device',
                'type': 'Smart Plug',
                'status': 'unknown',
                'online': False,
                'uuid': device_id,
                'id': device_id
            }
            
    except Exception as e:
        print(f"Error getting Matter status for {device_id}: {e}")
        return {
            'name': device_name or 'Matter Device',
            'type': 'Smart Plug',
            'status': 'unknown',
            'online': False,
            'uuid': device_id,
            'id': device_id,
            'error': str(e)
        }


async def control_matter(device_id, action, ip=None, port=5540):
    """Control a Matter device"""
    if not MATTER_AVAILABLE:
        return {'success': False, 'error': 'Matter library not available'}
    
    try:
        controller = MatterController(device_id, ip, port)
        
        if not await controller.connect():
            return {'success': False, 'error': 'Could not connect to device'}
        
        if action == 'on':
            result = await controller.turn_on()
        elif action == 'off':
            result = await controller.turn_off()
        elif action == 'toggle':
            # Get current status first
            status = await controller.get_status()
            current_state = status.get('status') == 'on'
            
            if current_state:
                result = await controller.turn_off()
            else:
                result = await controller.turn_on()
        else:
            controller.disconnect()
            return {'success': False, 'error': 'Invalid action'}
        
        controller.disconnect()
        
        if result:
            return {'success': True, 'action': action}
        else:
            return {'success': False, 'error': 'Command failed'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}


async def control_meross_async(uuid, action):
    """Control a Meross device (async)"""
    global meross_devices

    try:
        device = None
        for d in meross_devices:
            if d.uuid == uuid:
                device = d
                break

        if not device:
            return {'success': False, 'error': 'Device not found'}

        # Update device first to get current state
        await device.async_update()

        # Execute control action
        if action == 'on':
            await device.async_turn_on()
        elif action == 'off':
            await device.async_turn_off()
        elif action == 'toggle':
            current_state = device.is_on()
            if current_state:
                await device.async_turn_off()
            else:
                await device.async_turn_on()
        else:
            return {'success': False, 'error': 'Invalid action'}

        # Wait a moment for the command to take effect
        await asyncio.sleep(0.5)

        # Update again to get new state
        await device.async_update()

        return {
            'success': True,
            'action': action,
            'new_status': 'on' if device.is_on() else 'off'
        }
    except Exception as e:
        print(f"Error controlling Meross device: {e}")
        return {'success': False, 'error': str(e)}


# Routes

@app.before_request
def ensure_initialized():
    """Ensure app is initialized before handling requests"""
    if not _initialized:
        initialize_app()

@app.route('/')
def index():
    """Serve the main HTML page"""
    # Use project root directory (parent of api/)
    project_root = Path(__file__).parent.parent
    return send_from_directory(str(project_root), 'index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve static files from assets directory"""
    # Use project root directory (parent of api/)
    project_root = Path(__file__).parent.parent
    return send_from_directory(str(project_root / 'assets'), filename)


@app.route('/api/server/status', methods=['GET'])
def get_server_status():
    """Get server status including start time"""
    return jsonify({
        'success': True,
        'server_start_time': SERVER_START_TIME,
        'current_time': time.time()
    })


@app.route('/api/debug/tapo', methods=['GET'])
def debug_tapo_devices():
    """Debug endpoint to see what Tapo devices are configured"""
    tapo_config = {}
    for name, ip in KNOWN_DEVICES.items():
        if 'tapo' in name.lower():
            tapo_config[name] = ip
    
    return jsonify({
        'success': True,
        'known_devices': tapo_config,
        'dynamic_devices': tapo_devices_storage,
        'total_known': len(tapo_config),
        'total_dynamic': len(tapo_devices_storage)
    })


@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Get all devices status - optimized with parallel loading"""
    try:
        # Prepare Tapo device loading function
        def load_tapo_devices():
            """Load all Tapo devices in parallel"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                global tapo_devices_list
                tapo_devices = []
                tapo_devices_list = []  # Reset list for timeseries collection
                
                # Collect all Tapo devices to load in parallel
                tapo_tasks = []
                
                # Get devices from KNOWN_DEVICES (legacy)
                for name, ip in KNOWN_DEVICES.items():
                    if 'tapo' in name.lower():
                        tapo_devices_list.append({
                            'device_id': name,
                            'ip': ip,
                            'email': None,
                            'password': None,
                            'name': name.replace('tapo_', '').replace('_', ' ').title()
                        })
                        tapo_tasks.append((name, ip, None, None, name))
                
                # Get devices from dynamic storage
                for device_id, device_info in tapo_devices_storage.items():
                    ip = device_info.get('ip')
                    email = device_info.get('email')
                    password = device_info.get('password')
                    device_name = device_info.get('name', device_id)
                    
                    tapo_devices_list.append({
                        'device_id': device_id,
                        'ip': ip,
                        'email': email,
                        'password': password,
                        'name': device_name
                    })
                    tapo_tasks.append((device_id, ip, email, password, device_name))
                
                # Load all Tapo devices in parallel
                async def load_all_tapo_devices():
                    tasks = []
                    for device_id, ip, email, password, device_name in tapo_tasks:
                        tasks.append(get_tapo_status(ip, email, password, device_name))
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    for i, result in enumerate(results):
                        device_id, ip, email, password, device_name = tapo_tasks[i]
                        
                        if isinstance(result, Exception):
                            display_name = device_name.replace('tapo_', '').replace('_', ' ').title()
                            if display_name.endswith(' Monitor'):
                                display_name = display_name[:-8]
                            status = {
                                'name': display_name,
                                'type': 'Smart Plug',
                                'ip': ip,
                                'status': 'unknown',
                                'online': False,
                                'id': device_id
                            }
                            tapo_devices.append(status)
                        else:
                            result['id'] = device_id
                            tapo_devices.append(result)
                
                if tapo_tasks:
                    loop.run_until_complete(load_all_tapo_devices())
                
                return tapo_devices
            finally:
                loop.close()
        
        # Prepare Matter device loading function
        def load_matter_devices():
            """Load all Matter devices"""
            if not MATTER_AVAILABLE:
                return []
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                global matter_devices_list
                matter_devices = []
                matter_devices_list = []  # Reset list for timeseries collection
                
                all_matter_devices = get_all_matter_devices()
                
                async def load_all_matter_devices():
                    tasks = []
                    for device_info in all_matter_devices:
                        device_id = device_info['device_id']
                        ip = device_info.get('ip')
                        port = device_info.get('port', 5540)
                        device_name = device_info.get('name', device_id)
                        
                        matter_devices_list.append({
                            'device_id': device_id,
                            'ip': ip,
                            'name': device_name,
                            'port': port
                        })
                        
                        tasks.append(get_matter_status(device_id, ip, port, device_name))
                    
                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for i, result in enumerate(results):
                            if isinstance(result, Exception):
                                device_info = all_matter_devices[i]
                                matter_devices.append({
                                    'name': device_info.get('name', device_info['device_id']),
                                    'type': 'Smart Plug',
                                    'uuid': device_info['device_id'],
                                    'id': device_info['device_id'],
                                    'status': 'unknown',
                                    'online': False
                                })
                            else:
                                matter_devices.append(result)
                
                if all_matter_devices:
                    loop.run_until_complete(load_all_matter_devices())
                
                return matter_devices
            finally:
                loop.close()

        # Load all four device types in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all four tasks simultaneously
            tapo_future = executor.submit(load_tapo_devices)
            meross_future = executor.submit(lambda: run_in_meross_loop(get_meross_status_async()))
            arlec_future = executor.submit(get_arlec_status)
            matter_future = executor.submit(load_matter_devices)
            
            # Wait for all to complete and get results
            tapo_devices = tapo_future.result()
            meross_status = meross_future.result()
            arlec_status = arlec_future.result()
            matter_status = matter_future.result()

        # Populate Arlec devices list for timeseries collection
        global arlec_devices_list
        arlec_devices_list = []
        for device in arlec_status:
            if device.get('online') and device.get('uuid'):
                arlec_devices_list.append(device['uuid'])

        return jsonify({
            'success': True,
            'tapo': tapo_devices,
            'meross': meross_status,
            'arlec': arlec_status,
            'matter': matter_status
        })
    except Exception as e:
        print(f"Error in get_devices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tapo/<device_id>/<action>', methods=['POST'])
def control_tapo_device(device_id, action):
    """Control a Tapo device"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Check dynamic storage first, then fall back to KNOWN_DEVICES
        device_info = tapo_devices_storage.get(device_id)
        if device_info:
            ip = device_info.get('ip')
            email = device_info.get('email')
            password = device_info.get('password')
        else:
            ip = KNOWN_DEVICES.get(device_id)
            email = None
            password = None
        
        if not ip:
            return jsonify({'success': False, 'error': 'Device not found'}), 404

        result = loop.run_until_complete(control_tapo(ip, action, email, password))
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@app.route('/api/tapo/add', methods=['POST'])
def add_tapo_device():
    """Add a new Tapo device"""
    try:
        data = request.get_json()
        device_name = data.get('name', '').strip()
        ip = data.get('ip', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()

        if not device_name or not ip or not email or not password:
            return jsonify({'success': False, 'error': 'Missing required fields: name, ip, email, password'}), 400

        # Test connection first
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(get_tapo_status(ip, email, password))
            if not status.get('online'):
                return jsonify({'success': False, 'error': 'Could not connect to device. Check IP and credentials.'}), 400
        finally:
            loop.close()

        # Generate device ID from IP (more unique)
        device_id = f"tapo_{ip.replace('.', '_')}"
        
        # If device already exists, update it
        if device_id in tapo_devices_storage:
            return jsonify({
                'success': False,
                'error': f'Device with IP {ip} already exists'
            }), 400
        
        # Store device info
        tapo_devices_storage[device_id] = {
            'ip': ip,
            'email': email,
            'password': password,
            'name': device_name
        }
        
        # Save to file
        save_tapo_devices()

        return jsonify({
            'success': True,
            'device_id': device_id,
            'message': f'Device "{device_name}" added successfully'
        })
    except Exception as e:
        print(f"Error adding Tapo device: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/meross/<uuid>/<action>', methods=['POST'])
def control_meross_device(uuid, action):
    """Control a Meross device"""
    try:
        # Use the dedicated Meross event loop
        result = run_in_meross_loop(control_meross_async(uuid, action))
        return jsonify(result)
    except Exception as e:
        print(f"Error in control_meross_device: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/matter/<device_id>/<action>', methods=['POST'])
def control_matter_device(device_id, action):
    """Control a Matter device"""
    if not MATTER_AVAILABLE:
        return jsonify({'success': False, 'error': 'Matter library not available'}), 503
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Get device info from MATTER_DEVICES
        device_info = MATTER_DEVICES.get(device_id)
        if not device_info:
            # Try to find by device_id in all devices
            all_devices = get_all_matter_devices()
            device_info = None
            for dev in all_devices:
                if dev['device_id'] == device_id:
                    device_info = dev
                    break
        
        if not device_info:
            return jsonify({'success': False, 'error': 'Device not found'}), 404
        
        ip = device_info.get('ip')
        port = device_info.get('port', 5540)
        
        result = loop.run_until_complete(control_matter(device_id, action, ip, port))
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()


@app.route('/api/arlec/<uuid>/<action>', methods=['POST'])
def control_arlec_device(uuid, action):
    """Control an Arlec device (using uuid to match Meross API format)"""
    try:
        result = control_arlec(uuid, action)
        return jsonify(result)
    except Exception as e:
        print(f"Error in control_arlec_device: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/timeseries', methods=['GET'])
def get_timeseries():
    """Get timeseries power data - now handled client-side only"""
    # Return empty data - client will use localStorage cache
    return jsonify({
        'success': True,
        'timeseries': {}
    })


@app.route('/api/timeseries', methods=['POST'])
def add_timeseries_data():
    """Add timeseries data point from client - now handled client-side only"""
    # No-op endpoint for compatibility, data is stored in browser localStorage
    return jsonify({
        'success': True,
        'message': 'Data stored client-side'
    })


@app.route('/api/aemo/prices', methods=['GET'])
def get_aemo_prices():
    """Get AEMO price data for VIC region (constant $0.15/kWh for now)"""
    try:
        # Get interval parameter (in seconds) to determine date range
        interval_param = request.args.get('interval', '1800')  # Default 30 minutes
        try:
            interval_seconds = int(interval_param)
        except ValueError:
            interval_seconds = 1800

        # Calculate time range
        now = datetime.now()
        start_time = now - timedelta(seconds=interval_seconds)
        
        # Generate 5-minute interval timestamps
        prices = []
        current_time = start_time
        
        # Round start_time to nearest 5-minute mark
        minutes = current_time.minute
        rounded_minutes = (minutes // 5) * 5
        current_time = current_time.replace(minute=rounded_minutes, second=0, microsecond=0)
        
        # Generate price data points at 5-minute intervals
        while current_time <= now:
            prices.append({
                'timestamp': current_time.isoformat(),
                'price': 0.15  # Constant $0.15/kWh for now
            })
            current_time += timedelta(minutes=5)
        
        # Add forecast prices (next 30 minutes, 6 points at 5-minute intervals)
        forecast_start = now.replace(second=0, microsecond=0)
        forecast_minutes = (forecast_start.minute // 5) * 5
        if forecast_minutes < forecast_start.minute:
            forecast_minutes += 5
            # Handle rollover to next hour if minutes exceed 59
            if forecast_minutes >= 60:
                forecast_minutes = 0
                forecast_start = forecast_start.replace(hour=forecast_start.hour + 1, minute=0)
            else:
                forecast_start = forecast_start.replace(minute=forecast_minutes)
        else:
            forecast_start = forecast_start.replace(minute=forecast_minutes)
        
        for i in range(6):  # 6 × 5 minutes = 30 minutes forecast
            forecast_time = forecast_start + timedelta(minutes=i * 5)
            prices.append({
                'timestamp': forecast_time.isoformat(),
                'price': 0.15,  # Constant $0.15/kWh for now
                'forecast': True
            })
        
        return jsonify({
            'success': True,
            'region': 'VIC',
            'prices': prices
        })
    except Exception as e:
        print(f"Error in get_aemo_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/nem/prices/latest', methods=['GET'])
def get_nem_prices_latest():
    """Get latest NEM price data from cache file"""
    try:
        import os
        from pathlib import Path

        # Path to NEM price cache file
        cache_file = Path(__file__).parent.parent / 'power_price' / 'nem_price_cache.json'

        if not os.path.exists(cache_file):
            return jsonify({
                'success': False,
                'error': 'NEM price cache file not found'
            }), 404

        # Load cache file
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        # Extract latest data from each type
        result = {
            'metadata': cache_data.get('metadata', {}),
            'series': []
        }

        for data_type in ['dispatch', 'p5min', 'predispatch']:
            if data_type in cache_data and cache_data[data_type]:
                # Get the latest timestamp
                latest_timestamp = max(cache_data[data_type].keys())
                data = cache_data[data_type][latest_timestamp]

                # Format prices for Chart.js
                formatted_prices = []
                for point in data.get('prices', []):
                    formatted_prices.append({
                        'x': point['timestamp'],
                        'y': point['price']
                    })

                result['series'].append({
                    'name': data_type,
                    'data': formatted_prices,
                    'label': {
                        'dispatch': 'Dispatch (Actual)',
                        'p5min': 'P5MIN (5-min Forecast)',
                        'predispatch': 'Pre-dispatch (30min+ Forecast)'
                    }.get(data_type, data_type)
                })

        return jsonify(result)

    except Exception as e:
        print(f"Error in get_nem_prices_latest: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/mongodb/prices', methods=['GET'])
def get_mongodb_prices():
    """Get Historical (historical_price.price) and Forecast (Forecast_Price) data from MongoDB for a specific region and time range"""
    try:
        from pymongo.mongo_client import MongoClient
        from pymongo.server_api import ServerApi
        from pymongo.errors import ConnectionFailure
        from datetime import datetime
        import pytz
        
        # Get parameters
        region = request.args.get('region', 'VIC1')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        
        # MongoDB connection details (from IoS_logins.py)
        DB_NAME = MONGO_DB_NAME
        COLLECTION_NAME = MONGO_COLLECTION_NAME
        
        # Connect to MongoDB using centralized connection
        try:
            from mongodb.connection import connect_mongo, DB_NAME, PRICE_COLLECTION_NAME
            client = connect_mongo()
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to MongoDB'
                }), 500
        except ImportError:
            # Fallback if mongodb module not available
            from pymongo.mongo_client import MongoClient
            from pymongo.server_api import ServerApi
            from pymongo.errors import ConnectionFailure
            try:
                client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
                client.admin.command('ping')
            except ConnectionFailure as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to connect to MongoDB: {e}'
                }), 500
            DB_NAME = MONGO_DB_NAME
            PRICE_COLLECTION_NAME = MONGO_COLLECTION_NAME
        
        db = client[DB_NAME]
        collection = db[PRICE_COLLECTION_NAME]
        
        # Build query
        query = {'region': region}
        
        # Add time range if provided
        # MongoDB stores timestamps as ISO format strings, so we compare strings directly
        if start_time and end_time:
            try:
                # Normalize timestamps to ISO format strings
                # Remove 'Z' and ensure consistent format
                start_iso = start_time.replace('Z', '+00:00')
                end_iso = end_time.replace('Z', '+00:00')
                
                # MongoDB string comparison works correctly for ISO format timestamps
                query['timestamp'] = {
                    '$gte': start_iso,
                    '$lte': end_iso
                }
            except Exception as e:
                print(f"Error parsing time range: {e}")
        
        # Query MongoDB - sort by timestamp ascending
        documents = collection.find(query).sort('timestamp', 1)
        
        # Format results - separate historical and forecast series
        historical_prices = []
        forecast_prices = []
        historical_5min_prices = []
        historical_30min_prices = []
        
        for doc in documents:
            timestamp = doc.get('timestamp')
            # Ensure timestamp is in ISO format
            if isinstance(timestamp, str):
                ts_str = timestamp
            else:
                ts_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
            
            # Historical series (historical_price.price from nested object)
            historical_price_obj = doc.get('historical_price')
            if historical_price_obj and isinstance(historical_price_obj, dict):
                historical_price_value = historical_price_obj.get('price')
                if historical_price_value is not None:
                    historical_prices.append({
                        'x': ts_str,
                        'y': float(historical_price_value)
                    })
            
            # Forecast 5-minute series (dispatch_5min.price from nested object)
            dispatch_5min_obj = doc.get('dispatch_5min')
            if dispatch_5min_obj and isinstance(dispatch_5min_obj, dict):
                dispatch_5min_value = dispatch_5min_obj.get('price')
                if dispatch_5min_value is not None:
                    historical_5min_prices.append({
                        'x': ts_str,
                        'y': float(dispatch_5min_value)
                    })
            
            # Forecast 30-minute series (dispatch_30min.price from nested object)
            dispatch_30min_obj = doc.get('dispatch_30min')
            if dispatch_30min_obj and isinstance(dispatch_30min_obj, dict):
                dispatch_30min_value = dispatch_30min_obj.get('price')
                if dispatch_30min_value is not None:
                    historical_30min_prices.append({
                        'x': ts_str,
                        'y': float(dispatch_30min_value)
                    })
            
            # Forecast series (Forecast_Price)
            forecast_price = doc.get('Forecast_Price')
            if forecast_price is not None:
                forecast_prices.append({
                    'x': ts_str,
                    'y': float(forecast_price)
                })
        
        client.close()
        
        return jsonify({
            'success': True,
            'region': region,
            'historical': historical_prices,
            'forecast': forecast_prices,
            'forecast_5min': historical_5min_prices,
            'forecast_30min': historical_30min_prices,
            'historical_count': len(historical_prices),
            'forecast_count': len(forecast_prices),
            'forecast_5min_count': len(historical_5min_prices),
            'forecast_30min_count': len(historical_30min_prices)
        })
        
    except Exception as e:
        print(f"Error in get_mongodb_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cost', methods=['GET'])
def get_cost_data():
    """Calculate cost based on power usage and price data - now handled client-side only"""
    # Return empty data - client will calculate from localStorage cache
    return jsonify({
        'success': True,
        'costs': []
    })


# ============================================================================
# Device Usage Data Collection API Endpoints
# ============================================================================

@app.route('/api/device-usage/history', methods=['GET'])
def get_device_usage_history():
    """Get historical device usage data from MongoDB for phone app"""
    if not DATA_COLLECTION_AVAILABLE:
        return jsonify({'success': False, 'error': 'Data collection module not available'}), 503
    
    try:
        from pymongo.mongo_client import MongoClient
        from pymongo.server_api import ServerApi
        from pymongo.errors import ConnectionFailure
        from datetime import datetime
        import pytz
        
        # Get parameters
        device_id = request.args.get('device_id')  # Optional filter
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        region = request.args.get('region', 'VIC1')
        
        # Validate time range
        if not start_time or not end_time:
            return jsonify({
                'success': False,
                'error': 'start_time and end_time parameters are required'
            }), 400
        
        # Connect to MongoDB using centralized connection
        try:
            from mongodb.connection import connect_mongo, DB_NAME, USAGE_COLLECTION_NAME
            client = connect_mongo()
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to MongoDB'
                }), 500
        except ImportError:
            # Fallback if mongodb module not available
            from data_collection.device_usage_collector import connect_mongo, DB_NAME, USAGE_COLLECTION_NAME
            client = connect_mongo()
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to MongoDB'
                }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to connect to MongoDB: {e}'
            }), 500
        
        try:
            db = client[DB_NAME]
            collection = db[USAGE_COLLECTION_NAME]
            
            # Build query
            query = {}
            if device_id:
                query['device_id'] = device_id
            if region:
                query['region'] = region
            
            # Add time range
            try:
                start_iso = start_time.replace('Z', '+00:00')
                end_iso = end_time.replace('Z', '+00:00')
                query['timestamp'] = {
                    '$gte': start_iso,
                    '$lte': end_iso
                }
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid time format: {e}'
                }), 400
            
            # Query MongoDB - sort by timestamp ascending
            documents = collection.find(query).sort('timestamp', 1)
            
            # Format results with cost calculation
            data = []
            for doc in documents:
                record = {
                    'device_id': doc.get('device_id'),
                    'device_name': doc.get('device_name'),
                    'device_type': doc.get('device_type'),
                    'timestamp': doc.get('timestamp'),
                    'power': doc.get('power'),
                    'voltage': doc.get('voltage'),
                    'current': doc.get('current'),
                    'status': doc.get('status'),
                    'online': doc.get('online'),
                    'price_per_kwh': doc.get('price_per_kwh'),
                    'price_source': doc.get('price_source'),
                    'status_changed': doc.get('status_changed', False),
                    'status_change_type': doc.get('status_change_type'),
                    'interval_count': doc.get('interval_count', 0)
                }
                
                # Calculate cost for this 5-minute interval
                # Cost = (power_watts / 1000) * (5 minutes / 60) * price_per_kwh
                if record['power'] is not None and record['price_per_kwh'] is not None:
                    power_kw = record['power'] / 1000.0
                    hours = 5.0 / 60.0  # 5 minutes in hours
                    record['cost'] = round(power_kw * hours * record['price_per_kwh'], 4)
                else:
                    record['cost'] = None
                
                data.append(record)
            
            return jsonify({
                'success': True,
                'region': region,
                'count': len(data),
                'data': data
            })
            
        finally:
            client.close()
            
    except Exception as e:
        print(f"Error in get_device_usage_history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/device-usage/summary', methods=['GET'])
def get_device_usage_summary():
    """Get summary statistics for device usage (total energy, cost, etc.)"""
    if not DATA_COLLECTION_AVAILABLE:
        return jsonify({'success': False, 'error': 'Data collection module not available'}), 503
    
    try:
        from pymongo.mongo_client import MongoClient
        from pymongo.server_api import ServerApi
        from datetime import datetime
        import pytz
        
        # Get parameters
        device_id = request.args.get('device_id')  # Optional filter
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        region = request.args.get('region', 'VIC1')
        
        # Validate time range
        if not start_time or not end_time:
            return jsonify({
                'success': False,
                'error': 'start_time and end_time parameters are required'
            }), 400
        
        # Connect to MongoDB using centralized connection
        try:
            from mongodb.connection import connect_mongo, DB_NAME, USAGE_COLLECTION_NAME
            client = connect_mongo()
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to MongoDB'
                }), 500
        except ImportError:
            # Fallback if mongodb module not available
            from data_collection.device_usage_collector import connect_mongo, DB_NAME, USAGE_COLLECTION_NAME
            client = connect_mongo()
            if not client:
                return jsonify({
                    'success': False,
                    'error': 'Failed to connect to MongoDB'
                }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to connect to MongoDB: {e}'
            }), 500
        
        try:
            db = client[DB_NAME]
            collection = db[USAGE_COLLECTION_NAME]
            
            # Build query
            query = {}
            if device_id:
                query['device_id'] = device_id
            if region:
                query['region'] = region
            
            # Add time range
            try:
                start_iso = start_time.replace('Z', '+00:00')
                end_iso = end_time.replace('Z', '+00:00')
                query['timestamp'] = {
                    '$gte': start_iso,
                    '$lte': end_iso
                }
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid time format: {e}'
                }), 400
            
            # Query MongoDB
            documents = list(collection.find(query).sort('timestamp', 1))
            
            # Calculate summary statistics
            total_energy_kwh = 0.0
            total_cost = 0.0
            power_values = []
            on_count = 0
            total_count = len(documents)
            
            for doc in documents:
                power = doc.get('power')
                price = doc.get('price_per_kwh')
                status = doc.get('status')
                
                if power is not None:
                    power_values.append(power)
                    # Energy for 5-minute interval: (power_watts / 1000) * (5/60) hours
                    energy_kwh = (power / 1000.0) * (5.0 / 60.0)
                    total_energy_kwh += energy_kwh
                    
                    if price is not None:
                        cost = energy_kwh * price
                        total_cost += cost
                
                if status == 'on':
                    on_count += 1
            
            # Calculate statistics
            avg_power = sum(power_values) / len(power_values) if power_values else 0.0
            peak_power = max(power_values) if power_values else 0.0
            min_power = min(power_values) if power_values else 0.0
            
            # Calculate on-time (assuming 5-minute intervals)
            on_time_hours = (on_count * 5.0) / 60.0
            
            return jsonify({
                'success': True,
                'region': region,
                'device_id': device_id,
                'summary': {
                    'total_energy_kwh': round(total_energy_kwh, 3),
                    'total_cost': round(total_cost, 2),
                    'average_power_watts': round(avg_power, 2),
                    'peak_power_watts': round(peak_power, 2),
                    'min_power_watts': round(min_power, 2),
                    'on_time_hours': round(on_time_hours, 2),
                    'data_points': total_count,
                    'on_percentage': round((on_count / total_count * 100) if total_count > 0 else 0, 1)
                }
            })
            
        finally:
            client.close()
            
    except Exception as e:
        print(f"Error in get_device_usage_summary: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cron/collect-device-usage', methods=['GET', 'POST'])
def collect_device_usage_endpoint():
    """Endpoint for Vercel cron job to trigger device usage collection"""
    if not DATA_COLLECTION_AVAILABLE:
        return jsonify({'success': False, 'error': 'Data collection module not available'}), 503
    
    try:
        # Get region parameter (default: VIC1)
        region = request.args.get('region', 'VIC1')
        
        # Get all device statuses (reuse existing function)
        # We need to call get_devices() logic but get the data structure
        # For now, we'll call the device loading functions directly
        
        # Load Tapo devices
        def load_tapo_devices():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tapo_devices = []
                tapo_tasks = []
                
                for name, ip in KNOWN_DEVICES.items():
                    if 'tapo' in name.lower():
                        tapo_tasks.append((name, ip, None, None, name))
                
                for device_id, device_info in tapo_devices_storage.items():
                    ip = device_info.get('ip')
                    email = device_info.get('email')
                    password = device_info.get('password')
                    device_name = device_info.get('name', device_id)
                    tapo_tasks.append((device_id, ip, email, password, device_name))
                
                async def load_all():
                    tasks = [get_tapo_status(ip, email, password, device_name) 
                            for device_id, ip, email, password, device_name in tapo_tasks]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if not isinstance(result, Exception):
                            device_id = tapo_tasks[i][0]
                            result['id'] = device_id
                            tapo_devices.append(result)
                
                if tapo_tasks:
                    loop.run_until_complete(load_all())
                return tapo_devices
            finally:
                loop.close()
        
        # Load all devices in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            tapo_future = executor.submit(load_tapo_devices)
            meross_future = executor.submit(lambda: run_in_meross_loop(get_meross_status_async()))
            arlec_future = executor.submit(get_arlec_status)
            
            # Matter devices
            def load_matter():
                if not MATTER_AVAILABLE:
                    return []
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    all_matter = get_all_matter_devices()
                    async def load_all():
                        tasks = [get_matter_status(d['device_id'], d.get('ip'), d.get('port', 5540), d.get('name'))
                                for d in all_matter]
                        return await asyncio.gather(*tasks, return_exceptions=True)
                    if all_matter:
                        results = loop.run_until_complete(load_all())
                        return [r for r in results if not isinstance(r, Exception)]
                    return []
                finally:
                    loop.close()
            
            matter_future = executor.submit(load_matter)
            
            tapo_devices = tapo_future.result()
            meross_status = meross_future.result()
            arlec_status = arlec_future.result()
            matter_status = matter_future.result()
        
        # Format device statuses for collection
        device_statuses = {
            'tapo': tapo_devices,
            'meross': meross_status,
            'arlec': arlec_status,
            'matter': matter_status
        }
        
        # Collect and save
        result = collect_and_save(device_statuses, region=region)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in collect_device_usage_endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def start_meross_loop():
    """Start the dedicated Meross event loop in a background thread"""
    global meross_loop
    meross_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(meross_loop)
    meross_loop.run_forever()


def run_async_init():
    """Initialize async components in the Meross loop"""
    global meross_loop, meross_loop_thread

    # Start the dedicated event loop thread
    meross_loop_thread = Thread(target=start_meross_loop, daemon=True)
    meross_loop_thread.start()

    # Wait for loop to be ready
    time.sleep(0.5)

    # Initialize Meross in that loop
    try:
        run_in_meross_loop(init_meross())

        # Timeseries data collection is now handled client-side in the browser
    except Exception as e:
        print(f"Meross init error: {e}")


def collect_device_usage_background():
    """Background function to collect device usage data (for Flask server)"""
    if not DATA_COLLECTION_AVAILABLE:
        return
    
    try:
        # Get all device statuses by calling the endpoint logic
        # We'll reuse the collection endpoint's device loading logic
        region = 'VIC1'  # Default region
        
        # Load Tapo devices
        def load_tapo_devices():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tapo_devices = []
                tapo_tasks = []
                
                for name, ip in KNOWN_DEVICES.items():
                    if 'tapo' in name.lower():
                        tapo_tasks.append((name, ip, None, None, name))
                
                for device_id, device_info in tapo_devices_storage.items():
                    ip = device_info.get('ip')
                    email = device_info.get('email')
                    password = device_info.get('password')
                    device_name = device_info.get('name', device_id)
                    tapo_tasks.append((device_id, ip, email, password, device_name))
                
                async def load_all():
                    tasks = [get_tapo_status(ip, email, password, device_name) 
                            for device_id, ip, email, password, device_name in tapo_tasks]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if not isinstance(result, Exception):
                            device_id = tapo_tasks[i][0]
                            result['id'] = device_id
                            tapo_devices.append(result)
                
                if tapo_tasks:
                    loop.run_until_complete(load_all())
                return tapo_devices
            finally:
                loop.close()
        
        # Load all devices in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            tapo_future = executor.submit(load_tapo_devices)
            meross_future = executor.submit(lambda: run_in_meross_loop(get_meross_status_async()))
            arlec_future = executor.submit(get_arlec_status)
            
            # Matter devices
            def load_matter():
                if not MATTER_AVAILABLE:
                    return []
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    all_matter = get_all_matter_devices()
                    async def load_all():
                        tasks = [get_matter_status(d['device_id'], d.get('ip'), d.get('port', 5540), d.get('name'))
                                for d in all_matter]
                        return await asyncio.gather(*tasks, return_exceptions=True)
                    if all_matter:
                        results = loop.run_until_complete(load_all())
                        return [r for r in results if not isinstance(r, Exception)]
                    return []
                finally:
                    loop.close()
            
            matter_future = executor.submit(load_matter)
            
            tapo_devices = tapo_future.result()
            meross_status = meross_future.result()
            arlec_status = arlec_future.result()
            matter_status = matter_future.result()
        
        # Format device statuses for collection
        device_statuses = {
            'tapo': tapo_devices,
            'meross': meross_status,
            'arlec': arlec_status,
            'matter': matter_status
        }
        
        # Collect and save
        result = collect_and_save(device_statuses, region=region)
        
        if result.get('success'):
            print(f"[DATA COLLECTION] Collected {result.get('records_saved', 0)} device usage records")
        else:
            print(f"[DATA COLLECTION] Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"[DATA COLLECTION] Background collection error: {e}")


def collect_device_usage_30_seconds():
    """Collect device usage data every 30 seconds (adds to buffer)"""
    if not DATA_COLLECTION_AVAILABLE:
        return
    
    try:
        region = 'VIC1'  # Default region
        
        # Load all devices (same logic as 5-minute collection)
        def load_tapo_devices():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tapo_devices = []
                tapo_tasks = []
                
                for name, ip in KNOWN_DEVICES.items():
                    if 'tapo' in name.lower():
                        tapo_tasks.append((name, ip, None, None, name))
                
                for device_id, device_info in tapo_devices_storage.items():
                    ip = device_info.get('ip')
                    email = device_info.get('email')
                    password = device_info.get('password')
                    device_name = device_info.get('name', device_id)
                    tapo_tasks.append((device_id, ip, email, password, device_name))
                
                async def load_all():
                    tasks = [get_tapo_status(ip, email, password, device_name) 
                            for device_id, ip, email, password, device_name in tapo_tasks]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if not isinstance(result, Exception):
                            device_id = tapo_tasks[i][0]
                            result['id'] = device_id
                            tapo_devices.append(result)
                
                if tapo_tasks:
                    loop.run_until_complete(load_all())
                return tapo_devices
            finally:
                loop.close()
        
        # Load all devices in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            tapo_future = executor.submit(load_tapo_devices)
            meross_future = executor.submit(lambda: run_in_meross_loop(get_meross_status_async()))
            arlec_future = executor.submit(get_arlec_status)
            
            def load_matter():
                if not MATTER_AVAILABLE:
                    return []
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    all_matter = get_all_matter_devices()
                    async def load_all():
                        tasks = [get_matter_status(d['device_id'], d.get('ip'), d.get('port', 5540), d.get('name'))
                                for d in all_matter]
                        return await asyncio.gather(*tasks, return_exceptions=True)
                    if all_matter:
                        results = loop.run_until_complete(load_all())
                        return [r for r in results if not isinstance(r, Exception)]
                    return []
                finally:
                    loop.close()
            
            matter_future = executor.submit(load_matter)
            
            tapo_devices = tapo_future.result()
            meross_status = meross_future.result()
            arlec_status = arlec_future.result()
            matter_status = matter_future.result()
        
        # Format device statuses
        device_statuses = {
            'tapo': tapo_devices,
            'meross': meross_status,
            'arlec': arlec_status,
            'matter': matter_status
        }
        
        # Add to 30-second buffer (this will aggregate automatically at 5-minute intervals)
        from data_collection.device_usage_collector import collect_and_save
        result = collect_and_save(device_statuses, region=region)
        
        # Only print if we actually saved aggregated records (every 5 minutes)
        if result.get('success') and result.get('records_saved', 0) > 0:
            print(f"[DATA COLLECTION] Aggregated and saved {result.get('records_saved', 0)} device usage records (5-min avg)")
            
    except Exception as e:
        print(f"[DATA COLLECTION] 30-second collection error: {e}")


def start_data_collection_scheduler():
    """Start background scheduler for device usage collection (every 30 seconds)"""
    if not DATA_COLLECTION_AVAILABLE:
        print("[DATA COLLECTION] Module not available, skipping scheduler")
        return
    
    try:
        import schedule
        
        # Schedule collection every 30 seconds (adds to buffer)
        schedule.every(30).seconds.do(collect_device_usage_30_seconds)
        
        # Run scheduler in background thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)
        
        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        print("[DATA COLLECTION] Background scheduler started (every 30 seconds, aggregates to 5-min intervals)")
        
        # Run initial collection after 30 seconds (give server time to initialize)
        def initial_collection():
            time.sleep(30)
            collect_device_usage_30_seconds()
        
        initial_thread = Thread(target=initial_collection, daemon=True)
        initial_thread.start()
        
    except ImportError:
        print("[WARNING] 'schedule' library not found. Install with: pip install schedule")
        print("[DATA COLLECTION] Background scheduler not started")
    except Exception as e:
        print(f"[WARNING] Failed to start data collection scheduler: {e}")


# Initialization flag to prevent multiple initializations
_initialized = False

def initialize_app():
    """Initialize the application (devices, connections, etc.)"""
    global _initialized
    
    if _initialized:
        return
    
    try:
        # Load dynamically added Tapo devices from file
        load_tapo_devices()
    except Exception as e:
        print(f"[WARNING] Failed to load Tapo devices: {e}")
    
    try:
        # Initialize Arlec (Tuya Cloud)
        init_arlec()
    except Exception as e:
        print(f"[WARNING] Failed to initialize Arlec: {e}")
    
    try:
        # Initialize Meross with dedicated event loop
        run_async_init()
    except Exception as e:
        print(f"[WARNING] Failed to initialize Meross: {e}")
    
    # Start data collection scheduler (if available) - only for local development
    # On Vercel, cron jobs handle data collection
    is_vercel = os.getenv('VERCEL') is not None or os.getenv('VERCEL_ENV') is not None
    if not is_vercel:
        try:
            start_data_collection_scheduler()
        except Exception as e:
            print(f"[WARNING] Failed to start data collection scheduler: {e}")
    
    _initialized = True


# Initialize on module import (for Vercel serverless functions)
# This will run on cold start
# Use lazy initialization to avoid blocking on import
try:
    initialize_app()
except Exception as e:
    print(f"[WARNING] Initialization error (will retry on first request): {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("Smart Home Control Server")
    print("=" * 60)

    print("\n[OK] Server ready!")
    print("\nOpen your browser to:")
    print("  http://localhost:5000")
    print("\nPress Ctrl+C to stop")
    print("=" * 60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
