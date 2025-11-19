# Tapo Device Tools

This directory contains standalone utility scripts for Tapo devices. These scripts are not used by the main `server.py` but are useful for command-line control, testing, and device discovery.

## Available Scripts

- **tapo_controller.py** - Interactive CLI controller for Tapo devices
- **tapo_test.py** - Quick connectivity test script
- **scan_network.py** - Network scanner to find Tapo devices
- **find_tapo.py** - IP address finder utility

## Usage

All scripts can be run from this directory:

```bash
cd Tapo/_tools
python tapo_controller.py
```

Or from the project root:

```bash
python Tapo/_tools/tapo_controller.py
```

## Note

These tools are separate from the main web interface. For the integrated experience, use the main server at `http://localhost:5000` after running `python server.py`.

