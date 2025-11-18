# Tapo P100 WiFi Local Control

Python scripts to control TP-Link Tapo P100 smart plugs via local WiFi network.

## Prerequisites

- Python 3.6 or higher
- Tapo P100 smart plug connected to your WiFi network
- Tapo account credentials (email and password)
- The IP address of your Tapo P100 plug

## Finding Your Plug's IP Address

### Automated IP Finder (Recommended)

Use the included IP finder script to automatically scan your network:

```bash
python find_tapo.py
```

This script will:
- Scan your local network for devices
- Test which ones are Tapo devices
- Display all found Tapo P100 plugs with their IP addresses

### Quick Windows Method

Double-click `find_ip_simple.bat` to see all devices on your network using Windows ARP.

### Manual Methods

You can also find your Tapo P100's IP address manually:

1. **Tapo App** (Easiest):
   - Open Tapo app → Select your device → Settings (gear icon) → Device Info
   - Look for "IP Address"

2. **Router Admin Panel**:
   - Log into your router (usually 192.168.1.1 or 192.168.0.1)
   - Check "Connected Devices" or "DHCP Clients"
   - Look for device named "Tapo_Plug" or with TP-Link manufacturer

3. **Network Scanner Tools**:
   - Windows: `Advanced IP Scanner` (free download)
   - Mac/Linux: `nmap` command

## Installation

1. Navigate to this directory:
```bash
cd "plug/Tapo P100"
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

## Usage

### Quick Test Script

For a simple test to verify connectivity and basic on/off functionality:

```bash
python quick_test.py
```

This script will:
- Connect to your plug
- Display device information
- Turn the plug ON
- Wait for you to press Enter
- Turn the plug OFF

### Full Control Script

For an interactive menu with all control options:

```bash
python tapo_control.py
```

This script provides:
- Turn ON/OFF controls
- Toggle functionality
- Device information display
- Interactive menu interface

## Configuration

Your credentials are already configured in the scripts:
- Email: i.am.woods@gmail.com
- Password: Ch1cken1

**Security Note**: For production use, consider storing credentials in environment variables or a separate config file that's not committed to version control.

## Programmatic Usage

You can also import and use the TapoP100Controller class in your own scripts:

```python
from tapo_control import TapoP100Controller

# Initialize controller
controller = TapoP100Controller(
    ip_address="192.168.1.100",  # Your plug's IP
    email="i.am.woods@gmail.com",
    password="Ch1cken1"
)

# Connect
if controller.connect():
    # Turn on
    controller.turn_on()

    # Get info
    controller.get_device_info()

    # Turn off
    controller.turn_off()

    # Toggle
    controller.toggle()
```

## Troubleshooting

### Connection Issues

If you can't connect to the plug:

1. **Check IP Address**: Ensure the IP address is correct and the plug is online
2. **Network**: Make sure your computer and the plug are on the same WiFi network
3. **Credentials**: Verify your Tapo account email and password are correct
4. **Firewall**: Check if your firewall is blocking the connection
5. **Plug Reset**: Try resetting the plug and setting it up again in the Tapo app

### Common Errors

- **"No route to host"**: The IP address is incorrect or the plug is offline
- **"Authentication failed"**: Check your Tapo account credentials
- **"Timeout"**: The plug may be unreachable or on a different network

## Features

- Turn plug ON/OFF
- Toggle plug state
- Get device information (model, firmware version, MAC address, etc.)
- Interactive control menu
- Error handling and user-friendly messages

## Files

- `find_tapo.py`: Automated network scanner to find Tapo devices
- `find_ip_simple.bat`: Windows batch file for quick ARP scan
- `tapo_control.py`: Full-featured control script with interactive menu
- `quick_test.py`: Simple test script for quick connectivity check
- `requirements.txt`: Python package dependencies
- `config_example.ini`: Example configuration file
- `README.md`: This file

## API Information

This project uses the PyP100 library, which implements the Tapo P100 local control protocol. The library handles:
- Device handshake and authentication
- Encrypted communication with the plug
- State management and control commands

## License

This is a personal project for controlling Tapo P100 smart plugs.

## Notes

- The plug must be set up using the Tapo mobile app first
- Local control requires being on the same network as the plug
- The plug's IP address may change if your router uses DHCP (consider setting a static IP)
