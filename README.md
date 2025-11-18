# Smart Home Device Control Suite

Centralized control for Tapo and Meross smart home devices using Python.

## Overview

This project provides Python scripts to control:
- **Tapo** smart plugs (local WiFi control - supports P100, P110, and other models)
- **Meross** smart devices (cloud-based control)

All credentials are stored in a centralized `IoS_logins.py` file for easy management.

## Project Structure

```
plug/
├── IoS_logins.py          # Centralized credentials (DO NOT COMMIT)
├── .gitignore             # Protects sensitive files
├── README.md              # This file
├── requirements.txt       # Python dependencies for web server
│
├── server.py              # 🌐 Flask web server
├── index.html             # 🌐 Web interface
├── start_server.bat       # 🌐 Quick start script
│
├── Tapo/                 # Tapo device control (P100, P110, etc.)
│   ├── tapo_test.py      # Quick connectivity test
│   ├── tapo_controller.py # Interactive controller
│   ├── scan_network.py   # Network scanner
│   └── README.md         # Tapo documentation
│
└── Meross/               # Meross device control
    ├── discover_devices.py  # Device discovery
    ├── meross_test.py      # Quick connectivity test
    ├── meross_controller.py # Interactive controller
    ├── quick_demo.py       # Programmatic control demo
    └── README.md           # Meross documentation
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
cd "Tapo"
python tapo_controller.py
```

For Meross devices:
```bash
cd Meross
python meross_controller.py
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
python tapo_test.py

# Interactive control
python tapo_controller.py

# Find devices on network
python scan_network.py
```

### Meross Commands
```bash
# Discover all devices
python discover_devices.py

# Test connection
python meross_test.py

# Interactive control
python meross_controller.py
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

## Credits

- Uses the `tapo` library for TP-Link Tapo devices
- Uses the `meross_iot` library for Meross devices
