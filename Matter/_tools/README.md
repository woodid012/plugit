# Matter Device Tools

This directory contains standalone utility scripts for Matter devices. These scripts are not used by the main `server.py` but are useful for testing, discovery, and cloud configuration.

## Available Scripts

- **matter_test.py** - Quick connectivity test for Matter devices
- **discover_matter.py** - Device discovery and pairing utility
- **configure_cloud.py** - Cloud configuration helper for Matter devices

## Usage

All scripts can be run from this directory:

```bash
cd Matter/_tools
python matter_test.py
```

Or from the project root:

```bash
python Matter/_tools/matter_test.py
```

## Note

These tools are separate from the main web interface. For the integrated experience, use the main server at `http://localhost:5000` after running `python server.py`.

The main `Matter/matter_controller.py` is used by `server.py` and remains in the Matter directory root.

