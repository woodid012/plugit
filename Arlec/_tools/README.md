# Arlec Device Tools

This directory contains standalone utility scripts for Arlec devices. These scripts are not used by the main `server.py` but are useful for command-line control, testing, and device discovery.

## Available Scripts

- **arlec_controller.py** - Interactive CLI controller for local Arlec devices (via TinyTuya)
- **arlec_cloud_controller.py** - Interactive CLI controller for Arlec devices via Tuya Cloud API
- **arlec_test.py** - Quick connectivity test for local devices
- **arlec_cloud_test.py** - Quick connectivity test for cloud API
- **arlec_demo.py** - Automated demonstration script
- **test_commands.py** - Command format testing utility
- **scan_arlec.py** - Network scanner to find Arlec/Tuya devices

## Usage

All scripts can be run from this directory:

```bash
cd Arlec/_tools
python arlec_controller.py
```

Or from the project root:

```bash
python Arlec/_tools/arlec_controller.py
```

## Note

These tools are separate from the main web interface. For the integrated experience, use the main server at `http://localhost:5000` after running `python server.py`.

