# Matter Device Control

Python scripts to control Matter-compatible smart plugs with energy monitoring via local Matter protocol.

## Overview

Matter devices connect through the Matter protocol, which provides:
- Local WiFi control (similar to Tapo)
- Direct cloud upload capability (device uploads data independently)
- Energy monitoring support
- Standardized smart home protocol

## Prerequisites

- Python 3.7 or higher
- Matter-compatible smart plug with energy monitoring
- Matter device paired/commissioned on your network
- Matter Python libraries installed (see Installation)

## Installation

1. Navigate to this directory:
```bash
cd "plug/Matter"
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

### Required Libraries

The Matter controller requires one of the following Matter libraries:

- **python-matter-server** (recommended):
  ```bash
  pip install python-matter-server
  ```

- **matter-server** (alternative):
  ```bash
  pip install matter-server
  ```

- **zeroconf** (for device discovery):
  ```bash
  pip install zeroconf
  ```

**Note:** Matter Python support is still evolving. The actual library you need may depend on your specific Matter device. Check your device manufacturer's documentation for recommended Python libraries.

## Configuration

### 1. Add Device to IoS_logins.py

Edit `IoS_logins.py` in the parent directory and add your Matter device:

```python
MATTER_DEVICES = {
    'matter_device_1': {
        'device_id': '1234567890',  # Matter node ID (from device or pairing)
        'ip': '192.168.86.50',      # Optional: device IP address
        'name': 'Matter Smart Plug',
        'port': 5540                 # Optional: Matter server port
    }
}
```

### 2. Device Discovery and Pairing

If you don't know your device's ID or IP, use the discovery script:

```bash
python discover_matter.py
```

This will:
- Scan your network for Matter devices (via mDNS)
- Help you pair/commission new devices
- Display device information including IP addresses

### 3. Cloud Configuration (Optional)

To enable direct cloud upload from the device (not through your local machine):

```bash
python configure_cloud.py
```

This will help you configure:
- **AWS IoT Core** (recommended) - MQTT-based cloud service
- **MQTT Broker** - Public or self-hosted MQTT broker
- **REST API** - Custom HTTP endpoint

**Note:** Cloud configuration must be done on the device itself (via device firmware/app). This script generates the configuration you need to enter on the device.

## Usage

### Quick Test

Test connectivity and basic functionality:

```bash
python matter_test.py
```

This will:
- Connect to your Matter device
- Display device information
- Test energy monitoring
- Test on/off control
- Verify all functionality

### Interactive Controller

For full control with a menu interface:

```bash
python matter_controller.py
```

This provides:
- List all devices
- Turn devices ON/OFF
- Get device information
- Get energy usage data
- Interactive menu

### Device Discovery

Discover and pair Matter devices:

```bash
python discover_matter.py
```

## Integration with Web Server

Matter devices are automatically integrated into the main web server:

1. Start the server:
   ```bash
   python server.py
   ```

2. Open your browser to:
   ```
   http://localhost:5000
   ```

3. Matter devices will appear alongside Tapo, Meross, and Arlec devices

## Features

- **Local Control**: Direct WiFi connection to Matter device (no cloud required)
- **Energy Monitoring**: Real-time power, voltage, and current readings
- **Cloud Upload**: Device can upload data directly to cloud (AWS IoT, MQTT, or REST API)
- **Web Interface**: Integrated into main smart home control web UI
- **Timeseries Data**: Automatic power consumption tracking (24-hour history)
- **Device Discovery**: Automatic network scanning and pairing support

## How It Works

### Local Connection (Phase 1)
1. Matter device connects to your local WiFi network
2. Python controller communicates with device via Matter protocol
3. Direct local IP-based control (similar to Tapo)
4. No internet required for local control

### Cloud Upload (Phase 2)
1. Device is configured with cloud service credentials
2. Device uploads energy data directly to cloud (independent of local machine)
3. Local controller can also push data as backup
4. Cloud service stores and processes device data

## Troubleshooting

### Connection Issues

If you can't connect:

1. **Check Device ID**: Verify the device_id in MATTER_DEVICES matches your device
2. **Check IP Address**: Ensure device IP is correct (use discover_matter.py)
3. **Matter Server**: Some devices require a Matter server running (check device docs)
4. **Network**: Ensure device is on the same network as your computer
5. **Pairing**: Device may need to be paired/commissioned first

### Library Not Available

If you see "Matter library not available":

1. Install Matter libraries:
   ```bash
   pip install python-matter-server
   ```

2. Or try alternative:
   ```bash
   pip install matter-server
   ```

3. Check your device manufacturer's documentation for recommended library

### No Devices Found

If no devices are discovered:

1. Ensure device is powered on and connected to WiFi
2. Device may need to be in pairing mode
3. Try manual IP discovery (script will prompt)
4. Check firewall settings
5. Verify device supports Matter protocol

### Energy Monitoring Not Available

If energy data is not available:

1. Verify your device model supports energy monitoring
2. Check device firmware is up to date
3. Some devices require specific Matter clusters to be enabled
4. Energy monitoring may require device-specific configuration

## Cloud Service Setup

### AWS IoT Core (Recommended)

1. Create AWS account and IoT Core thing
2. Generate device certificates
3. Configure device policy
4. Use `configure_cloud.py` to generate configuration
5. Enter configuration on device (via device app/firmware)

### MQTT Broker

1. Choose MQTT broker (HiveMQ Cloud, Mosquitto, etc.)
2. Create account and get broker URL
3. Configure credentials in IoS_logins.py
4. Use `configure_cloud.py` to generate configuration
5. Enter configuration on device

### REST API

1. Set up HTTP endpoint (AWS API Gateway, Google Cloud Functions, etc.)
2. Configure API key authentication
3. Set REST_API_ENDPOINT and REST_API_KEY in IoS_logins.py
4. Use `configure_cloud.py` to generate configuration
5. Enter configuration on device

## Device Configuration

**Important:** Cloud upload configuration must be done on the device itself. The `configure_cloud.py` script generates the configuration you need, but you must enter it into your device via:

- Device mobile app
- Device web interface
- Device firmware configuration
- Matter commissioning tool

The device firmware handles the actual cloud upload - your local machine is not involved in the upload process.

## Supported Devices

Any Matter-compatible smart plug with energy monitoring should work. Tested with:
- Generic Matter smart plugs from China
- Devices supporting Matter OnOff cluster
- Devices supporting Matter Electrical Measurement cluster

## Programmatic Usage

You can import and use the MatterController in your own scripts:

```python
import asyncio
from Matter.matter_controller import MatterController

async def control_matter():
    controller = MatterController(
        device_id='1234567890',
        ip='192.168.86.50'
    )
    
    if await controller.connect():
        # Turn on
        await controller.turn_on()
        
        # Get energy data
        energy = await controller.get_energy_usage()
        print(f"Power: {energy['power']} W")
        
        # Turn off
        await controller.turn_off()
        
        controller.disconnect()

asyncio.run(control_matter())
```

## Security Notes

1. **IoS_logins.py** contains device credentials - keep it secure
2. **Cloud credentials** should be stored securely on the device
3. Use TLS/SSL for all cloud communications
4. Matter protocol includes built-in security features
5. Never commit credentials to version control

## Next Steps

1. **Pair your Matter device** using `discover_matter.py`
2. **Add device to MATTER_DEVICES** in IoS_logins.py
3. **Test connectivity** with `matter_test.py`
4. **Configure cloud upload** (optional) with `configure_cloud.py`
5. **Use web interface** at http://localhost:5000

## Support

For detailed information, see:
- `matter_controller.py` - Controller implementation
- `discover_matter.py` - Discovery and pairing
- `configure_cloud.py` - Cloud configuration
- Main `README.md` - Overall project documentation

## Credits

- Uses Matter protocol for device communication
- Compatible with Matter standard smart home devices
- Integrates with existing Tapo/Meross/Arlec control system



