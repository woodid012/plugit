# Meross Device Tools

This directory contains standalone utility scripts for Meross devices. These scripts are not used by the main `server.py` but are useful for command-line control, testing, and device discovery.

## Available Scripts

- **meross_controller.py** - Interactive CLI controller for Meross devices
- **meross_test.py** - Quick connectivity test script
- **discover_devices.py** - Device discovery utility

## Usage

All scripts can be run from this directory:

```bash
cd Meross/_tools
python meross_controller.py
```

Or from the project root:

```bash
python Meross/_tools/meross_controller.py
```

## Note

These tools are separate from the main web interface. For the integrated experience, use the main server at `http://localhost:5000` after running `python server.py`.

