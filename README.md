# Smart Home Device Control Suite

Centralized control for Tapo, Meross, Arlec, and Matter smart home devices using Python.

## Overview

This project provides Python scripts to control:
- **Tapo** smart plugs (local WiFi control - supports P100, P110, and other models)
- **Meross** smart devices (cloud-based control)
- **Arlec** smart plugs (Tuya protocol - local and cloud control)
- **Matter** smart devices (Matter protocol - local control with cloud upload capability)

Plus integration with **NEMweb** for real-time electricity price data.

All credentials are stored in a centralized `IoS_logins.py` file for easy management.

## Project Structure

```
plug/
├── IoS_logins.py          # Centralized credentials (DO NOT COMMIT)
├── .gitignore             # Protects sensitive files
├── README.md              # This file
├── requirements.txt       # Python dependencies for web server
│
├── server.py              # 🌐 Flask web server (main entry point)
├── index.html             # 🌐 Web interface
├── start_server.bat       # 🌐 Quick start script
│
├── Tapo/                  # Tapo device control (P100, P110, etc.)
│   ├── README.md          # Tapo documentation
│   ├── requirements.txt   # Tapo dependencies
│   └── _tools/           # Standalone CLI utilities
│       ├── tapo_controller.py
│       ├── tapo_test.py
│       ├── scan_network.py
│       └── find_tapo.py
│
├── Meross/                # Meross device control
│   ├── README.md          # Meross documentation
│   ├── requirements.txt   # Meross dependencies
│   └── _tools/           # Standalone CLI utilities
│       ├── meross_controller.py
│       ├── meross_test.py
│       └── discover_devices.py
│
├── Arlec/                 # Arlec device control (Tuya)
│   ├── README.md          # Arlec documentation
│   ├── requirements.txt   # Arlec dependencies
│   └── _tools/           # Standalone CLI utilities
│       ├── arlec_controller.py
│       ├── arlec_cloud_controller.py
│       ├── arlec_test.py
│       └── [other utilities]
│
├── Matter/                # Matter device control
│   ├── README.md          # Matter documentation
│   ├── requirements.txt   # Matter dependencies
│   ├── matter_controller.py  # Used by server.py
│   └── _tools/           # Standalone utilities
│       ├── matter_test.py
│       ├── discover_matter.py
│       └── configure_cloud.py
│
├── power_price/           # NEMweb price data fetcher
│   ├── README.md          # Power price documentation
│   ├── fetch_prices.py    # Main price fetcher (used by server.py)
│   ├── nem_price_cache.json  # Price data cache
│   └── __init__.py
│
└── _standalone/           # Standalone components (not integrated)
    ├── power_price_api_server.py
    ├── power_price_dashboard.html
    └── [other standalone utilities]
```

## Quick Start

### 1. Install Dependencies

```bash
cd plug
pip install -r requirements.txt
```

### 2. Configure Credentials

Your credentials are already set in `IoS_logins.py`:

- **Tapo Account:** i.am.woods@gmail.com
- **Meross Account:** dbwooding88@gmail.com

⚠️ **IMPORTANT:** Never commit `IoS_logins.py` to version control!

### 3. Control Your Devices

**🌐 WEB INTERFACE (RECOMMENDED):**

The easiest way to control all your devices in one place!

```bash
# Start the web server
python server.py

# Then open your browser to:
http://localhost:5000
```

Or simply double-click `start_server.bat`

Features:
- ✨ Beautiful, modern web interface
- 📱 Control all devices from one page
- 🔄 Auto-refresh every 30 seconds
- 🎯 Grouped by device type (Tapo vs Meross)
- ⚡ Real-time device status
- 🎨 Responsive design

**Command Line Alternative:**

For Tapo:
```bash
python Tapo/_tools/tapo_controller.py
```

For Meross devices:
```bash
python Meross/_tools/meross_controller.py
```

For Arlec devices:
```bash
python Arlec/_tools/arlec_controller.py
# or for cloud control:
python Arlec/_tools/arlec_cloud_controller.py
```

For Matter devices:
```bash
python Matter/_tools/matter_test.py
```

## Your Connected Devices

### Tapo Devices
- **Wine Fridge** @ 192.168.86.37

### Meross Devices (4 total)
1. **Dryer** (mss310) - Status: ON
2. **Washing machine** (mss310) - Status: ON
3. **Dishwasher** (mss310) - Status: ON
4. **Fridge** (mss310) - Status: ON

## Key Differences

| Feature | Tapo | Meross |
|---------|------|--------|
| Connection | Local WiFi | Cloud API |
| Internet Required | No | Yes |
| Device Discovery | Manual IP | Automatic |
| Remote Access | Via Tapo cloud | Built-in |
| Response Time | Fast | Moderate |
| Setup | Tapo app | Meross app |

## Common Commands

### Tapo Commands
```bash
# Test connection
python Tapo/_tools/tapo_test.py

# Interactive control
python Tapo/_tools/tapo_controller.py

# Find devices on network
python Tapo/_tools/scan_network.py
```

### Meross Commands
```bash
# Discover all devices
python Meross/_tools/discover_devices.py

# Test connection
python Meross/_tools/meross_test.py

# Interactive control
python Meross/_tools/meross_controller.py
```

### Arlec Commands
```bash
# Test local connection
python Arlec/_tools/arlec_test.py

# Test cloud connection
python Arlec/_tools/arlec_cloud_test.py

# Interactive local control
python Arlec/_tools/arlec_controller.py

# Interactive cloud control
python Arlec/_tools/arlec_cloud_controller.py
```

### Matter Commands
```bash
# Test connection
python Matter/_tools/matter_test.py

# Discover devices
python Matter/_tools/discover_matter.py

# Configure cloud upload
python Matter/_tools/configure_cloud.py
```

## Security Notes

1. **IoS_logins.py** contains sensitive credentials - it's automatically ignored by git
2. For production use, consider environment variables or encrypted storage
3. Keep your Tapo and Meross app credentials secure
4. The Tapo plug IP may change if using DHCP - consider setting a static IP

## Troubleshooting

### Tapo Issues
- **Can't connect:** Verify IP address and ensure device is on same WiFi network
- **Timeout:** Check firewall settings
- **Wrong credentials:** Update `IoS_logins.py`

### Meross Issues
- **No devices found:** Ensure devices are set up in Meross app
- **Login failed:** Check credentials in `IoS_logins.py`
- **Connection timeout:** Verify internet connection

## Files to Keep Secure

These files contain credentials and should NEVER be committed:
- `IoS_logins.py` ⚠️
- Any `config.py` or `credentials.py` files
- `.env` files

## Next Steps

1. **Set static IP for Tapo device** (via router) to prevent IP changes
2. **Create automation scripts** using the controller classes
3. **Add scheduling** for automatic device control
4. **Monitor energy usage** (Meross MSS310 supports this)

## Support

For detailed information, see:
- `Tapo/README.md` - Tapo-specific documentation
- `Meross/README.md` - Meross-specific documentation
- `Arlec/README.md` - Arlec-specific documentation
- `Matter/README.md` - Matter-specific documentation
- `power_price/README.md` - Power price data documentation
- `_standalone/README.md` - Standalone components documentation

## Project Organization

- **Main System**: `server.py` and `index.html` provide the integrated web interface
- **Device Modules**: Each device type (Tapo, Meross, Arlec, Matter) has its own directory with:
  - `README.md` - Module documentation
  - `requirements.txt` - Module dependencies
  - `_tools/` - Standalone CLI utilities (not used by server.py)
- **Standalone Components**: `_standalone/` contains independent utilities that can be run separately
- **Power Price**: `power_price/` module is integrated into server.py for real-time price data

## Credits

- Uses the `tapo` library for TP-Link Tapo devices
- Uses the `meross_iot` library for Meross devices
