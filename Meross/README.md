# Meross Device Control

Python scripts to control Meross smart home devices (smart plugs, switches, bulbs, garage door openers, etc.) via the Meross Cloud API.

## Overview

Meross devices connect through the Meross cloud service, which means:
- You need your Meross account credentials (email/password)
- Devices must be set up in the Meross mobile app first
- Internet connection is required
- The scripts will discover ALL devices registered to your account
- Control works even when you're away from home

## Prerequisites

- Python 3.7 or higher
- Meross devices set up in the Meross mobile app
- Meross account credentials (email and password)
- Internet connection

## Installation

1. Navigate to this directory:
```bash
cd "plug/Meross"
```

2. Install required Python packages:
```bash
pip install -r requirements.txt
```

## Usage

### 1. Device Discovery

First, discover all devices on your account:

```bash
python discover_devices.py
```

This will:
- Connect to your Meross cloud account
- List all registered devices
- Show device names, types, models, and online status
- Display local IP addresses (if available)
- Show power status for switches/plugs

### 2. Quick Test

Test connectivity and basic control:

```bash
python meross_test.py
```

This script will:
- Connect to Meross cloud
- Discover all your devices
- Display detailed information
- Test ON/OFF control on the first device

### 3. Interactive Controller

For full control with a menu interface:

```bash
python meross_controller.py
```

This provides:
- List all devices
- Turn devices ON/OFF
- Toggle device state
- Get detailed device information
- Refresh device status
- Control multiple devices

## Configuration

Your credentials are already configured in the scripts:
- Email: i.am.woods@gmail.com
- Password: Ch1cken1

**Security Note**: For production use, consider using environment variables or a separate config file.

## Supported Devices

The Meross library supports many device types:
- **Smart Plugs** (MSS110, MSS210, MSS310, etc.)
- **Smart Switches** (MSS510, MSS550, etc.)
- **Smart Bulbs** (MSL120, MSL320, etc.)
- **Garage Door Openers** (MSG100, MSG200)
- **Power Strips** (MSS425, MSS620)
- **Thermostat** (MTS100, MTS200)
- **Humidifiers**
- And more...

## Features

- Cloud-based control (works from anywhere)
- Automatic device discovery
- Multi-device support
- Real-time status updates
- Device information retrieval
- Support for multi-channel devices
- Power consumption monitoring (on supported devices)

## How It Works

1. **Authentication**: Scripts authenticate with Meross cloud using your credentials
2. **Device Discovery**: Meross cloud provides a list of all your registered devices
3. **Control**: Commands are sent through the Meross cloud to your devices
4. **Local Control**: Some devices support local LAN control for faster response

## Troubleshooting

### Connection Issues

If you can't connect:

1. **Check Credentials**: Verify your Meross account email and password
2. **Internet Connection**: Ensure you have an active internet connection
3. **Meross App**: Verify devices are visible in the Meross mobile app
4. **Account Status**: Make sure your Meross account is active

### No Devices Found

If no devices are discovered:

1. Open the Meross mobile app
2. Check that devices are registered to your account
3. Ensure devices are powered on
4. Verify devices show as "online" in the app
5. Try removing and re-adding a device in the app

### Common Errors

- **Authentication failed**: Wrong email or password
- **Timeout errors**: Internet connection issues
- **Device not responding**: Device is offline or unreachable

## Programmatic Usage

You can import and use the MerossController in your own scripts:

```python
import asyncio
from meross_controller import MerossController

async def control_meross():
    controller = MerossController(
        email="i.am.woods@gmail.com",
        password="Ch1cken1"
    )

    # Connect and discover
    if await controller.connect():
        # List devices
        await controller.list_devices()

        # Control first device (index 0)
        await controller.turn_on(0)
        await asyncio.sleep(2)
        await controller.turn_off(0)

        # Cleanup
        controller.cleanup()
        await controller.http_client.async_logout()

asyncio.run(control_meross())
```

## Files

- `discover_devices.py`: Device discovery and listing script
- `meross_test.py`: Quick test script for connectivity and basic control
- `meross_controller.py`: Interactive controller with menu
- `requirements.txt`: Python package dependencies
- `README.md`: This file

## API Information

This project uses the `meross_iot` library, which:
- Implements the Meross cloud API protocol
- Handles authentication and device management
- Provides async/await support for non-blocking operations
- Supports both cloud and local control

## Comparison with Tapo

| Feature | Meross | Tapo |
|---------|--------|------|
| Connection | Cloud-based | Local WiFi |
| Internet Required | Yes | No (after setup) |
| Remote Control | Built-in | Requires cloud |
| Setup | App required | App required |
| Device Discovery | Automatic via cloud | IP address needed |
| Response Time | Moderate | Fast |

## Notes

- All Meross devices must be set up using the Meross mobile app first
- The scripts use cloud API, so internet is required
- Some devices support local LAN control for faster responses
- Multi-channel devices (power strips) are fully supported
- Energy monitoring available on supported devices

## Links

- [Meross Official Website](https://www.meross.com/)
- [meross_iot Library on GitHub](https://github.com/albertogeniola/MerossIot)
- [Meross App Download](https://www.meross.com/app)

## License

This is a personal project for controlling Meross smart home devices.
