# Arlec Smart Plug Local Control

Python scripts to control Arlec smart plugs via local WiFi network using the TinyTuya library.

## Overview

Arlec smart devices use the Tuya protocol, which allows for local control without cloud dependency. This implementation uses TinyTuya to communicate directly with your Arlec smart plug over your local network.

## Prerequisites

- Python 3.6 or higher
- Arlec smart plug connected to your WiFi network
- Device credentials (Device ID, Local Key, IP Address)
- Arlec/Smart Life/Tuya app account

## Getting Device Credentials

To control Arlec devices locally, you need three pieces of information:
1. **Device ID**: Unique identifier for your device
2. **Local Key**: Encryption key for local communication
3. **IP Address**: Local network IP of your device

### Method 1: TinyTuya Wizard (Recommended)

The easiest way to get your credentials is using the TinyTuya wizard:

```bash
python -m tinytuya wizard
```

This interactive wizard will:
- Guide you through creating a Tuya IoT Platform account
- Help you link your Smart Life/Tuya app
- Scan your network for devices
- Extract Device IDs and Local Keys
- Display all your devices with their credentials

### Method 2: Manual Setup via Tuya IoT Platform

1. **Create Tuya Developer Account**:
   - Go to https://iot.tuya.com/
   - Sign up for a developer account
   - Create a Cloud Project

2. **Link Your Smart Life App**:
   - In the Tuya IoT Platform, go to "Cloud" → "Development"
   - Link your Smart Life/Tuya Smart app account
   - Your devices will appear in the platform

3. **Get Credentials**:
   - Device ID and Local Key are available in the device details
   - IP address can be found in your router or using network scanning tools

### Finding IP Address

You can find your Arlec plug's IP address:

1. **Router Admin Panel**:
   - Log into your router (usually 192.168.1.1 or 192.168.86.1)
   - Check "Connected Devices" or "DHCP Clients"
   - Look for device with "Tuya" or your device name

2. **Smart Life App**:
   - Open Smart Life app → Select device → Settings
   - Look for network or device information

3. **Network Scanner**:
   - Windows: `Advanced IP Scanner` (free download)
   - Mac/Linux: `nmap -sn 192.168.1.0/24`

## Installation

1. Navigate to this directory:
```bash
cd "plug/Arlec"
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

3. Update credentials in `../IoS_logins.py`:
```python
# Arlec Device Credentials
ARLEC_DEVICE_ID = "your_device_id_here"
ARLEC_DEVICE_IP = "192.168.1.xxx"
ARLEC_LOCAL_KEY = "your_local_key_here"
```

## Usage

### Quick Test Script

To verify connectivity and test basic functionality:

```bash
python arlec_test.py
```

This script will:
- Connect to your Arlec plug
- Display device information and status
- Turn the plug ON
- Turn the plug OFF
- Confirm everything is working

### Full Control Script

For interactive control with all features:

```bash
python arlec_controller.py
```

This provides:
- Turn ON/OFF controls
- Toggle functionality
- Device information display
- Status monitoring
- Energy monitoring (if supported by your model)
- Interactive menu interface

## Features

### Basic Controls
- Turn plug ON/OFF
- Toggle plug state
- Get current status

### Device Information
- Device ID and IP address
- Power state (ON/OFF)
- Current power consumption (Watts)
- Voltage (Volts)
- Current (mA)
- Total energy usage (kWh)
- All available Data Points (DPS)

### Energy Monitoring

Many Arlec smart plugs include energy monitoring. The controller displays:
- Real-time power consumption
- Voltage and current measurements
- Cumulative energy usage

## Programmatic Usage

You can import and use the ArlecController class in your own scripts:

```python
from arlec_controller import ArlecController

# Initialize controller
controller = ArlecController(
    device_id="your_device_id",
    ip_address="192.168.1.100",
    local_key="your_local_key"
)

# Connect
if controller.connect():
    # Turn on
    controller.turn_on()

    # Get device info
    controller.get_info()

    # Get status
    status = controller.get_status()

    # Turn off
    controller.turn_off()

    # Toggle
    controller.toggle()
```

## Troubleshooting

### Connection Issues

If you can't connect to the device:

1. **Verify Credentials**: Double-check Device ID, IP, and Local Key
2. **Network**: Ensure your computer and plug are on the same WiFi network
3. **Device Status**: Make sure the device is powered on and connected
4. **Protocol Version**: Most Arlec devices use protocol 3.3, but some may use 3.1 or 3.4
5. **Firewall**: Check if your firewall is blocking UDP port 6668

### Getting Credentials

If you're having trouble getting credentials:

1. Run the TinyTuya wizard: `python -m tinytuya wizard`
2. Make sure your Tuya IoT project has the correct permissions
3. Ensure your Smart Life app is linked to the IoT platform
4. Try unlinking and relinking your app in the IoT platform

### Common Errors

- **"Connection refused"**: Wrong IP address or device offline
- **"Decryption failed"**: Incorrect Local Key
- **"Device not found"**: Wrong Device ID or network issue
- **"Timeout"**: Device unreachable, check network and firewall

### Protocol Version

If the default protocol 3.3 doesn't work, try changing the version in the controller:

```python
# In arlec_controller.py, line 33:
version=3.3  # Try 3.1 or 3.4 if 3.3 doesn't work
```

## Understanding DPS (Data Points)

Tuya devices use "Data Points" (DPS) to represent different features:

Common DPS values for Arlec smart plugs:
- **DPS 1**: Switch state (True = ON, False = OFF)
- **DPS 9**: Countdown timer (seconds)
- **DPS 17**: Current (mA)
- **DPS 18**: Power (in 0.1W, divide by 10 for Watts)
- **DPS 19**: Voltage (in 0.1V, divide by 10 for Volts)
- **DPS 20**: Total energy (in 0.01kWh, divide by 100 for kWh)

Your device may have different DPS values. Use the `get_info()` function to see all available data points.

## Files

- `arlec_controller.py`: Full-featured control script with interactive menu
- `arlec_test.py`: Simple test script for quick connectivity check
- `requirements.txt`: Python package dependencies
- `README.md`: This file
- `.gitignore`: Git ignore patterns

## Technical Details

### TinyTuya Library

This project uses the TinyTuya library, which:
- Implements the Tuya local protocol
- Handles device handshake and encryption
- Supports multiple protocol versions
- Provides both synchronous control

### Communication Protocol

- **Protocol**: Tuya Local (UDP/TCP)
- **Port**: 6668 (default)
- **Encryption**: AES encryption using the Local Key
- **Version**: 3.3 (typical for Arlec devices)

## Security Notes

- Keep your Local Key secure and never commit it to version control
- The `.gitignore` file is configured to prevent credential exposure
- Local Key changes if you remove and re-add the device to your app
- Store credentials in environment variables for production use

## Additional Resources

- [TinyTuya GitHub](https://github.com/jasonacox/tinytuya)
- [TinyTuya Documentation](https://github.com/jasonacox/tinytuya/blob/master/README.md)
- [Tuya IoT Platform](https://iot.tuya.com/)
- [Smart Life App](https://www.tuya.com/smart-life)

## License

This is a personal project for controlling Arlec smart plugs locally.

## Notes

- The device must be set up using the Smart Life/Tuya app first
- Local control requires being on the same network as the device
- IP address may change if using DHCP (consider setting a static IP)
- Local Key changes if you reset or re-pair the device
- Some features may vary depending on your specific Arlec model
