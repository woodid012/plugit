"""
Quick test for Arlec Smart Plug using TinyTuya
Tests connection and basic on/off functionality
"""

import sys
import time
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import ARLEC_DEVICE_ID, ARLEC_DEVICE_IP, ARLEC_LOCAL_KEY

import tinytuya


def test_arlec():
    """Test connection to Arlec smart plug"""
    # Configuration
    DEVICE_ID = ARLEC_DEVICE_ID
    DEVICE_IP = ARLEC_DEVICE_IP
    LOCAL_KEY = ARLEC_LOCAL_KEY

    print("=" * 60)
    print("Arlec Smart Plug Connection Test")
    print("=" * 60)
    print(f"\nDevice ID:  {DEVICE_ID}")
    print(f"IP Address: {DEVICE_IP}")
    print(f"Local Key:  {'*' * len(LOCAL_KEY)}\n")

    try:
        # Create device connection
        print("Connecting to device...")
        device = tinytuya.OutletDevice(
            dev_id=DEVICE_ID,
            address=DEVICE_IP,
            local_key=LOCAL_KEY,
            version=3.3  # Most Arlec devices use protocol 3.3
        )

        # Set socket timeout
        device.set_socketTimeout(5)

        # Get initial status
        print("Getting device status...")
        status = device.status()

        if not status or 'dps' not in status:
            raise Exception(f"Failed to get device status: {status}")

        print("[OK] Connected successfully!")

        # Display device information
        print("\n" + "=" * 60)
        print("Device Information:")
        print("=" * 60)

        dps = status['dps']

        if '1' in dps:
            state = "ON" if dps['1'] else "OFF"
            print(f"Current State:   {state}")

        if '18' in dps:
            power_w = dps['18'] / 10
            print(f"Current Power:   {power_w:.1f} W")

        if '19' in dps:
            voltage_v = dps['19'] / 10
            print(f"Voltage:         {voltage_v:.1f} V")

        if '17' in dps:
            current_ma = dps['17']
            print(f"Current:         {current_ma} mA")

        print("\nAll DPS values:")
        for key, value in dps.items():
            print(f"  DPS {key}: {value}")

        print("=" * 60)

        # Test turning ON
        print("\nTesting control...")
        print("Turning plug ON...")
        device.turn_on()
        time.sleep(2)
        print("[OK] Plug is ON")

        # Test turning OFF
        print("\nTurning plug OFF...")
        device.turn_off()
        time.sleep(2)
        print("[OK] Plug is OFF")

        print("\n" + "=" * 60)
        print("SUCCESS! Your Arlec smart plug is working correctly!")
        print("=" * 60)
        print("\nYou can now use arlec_controller.py for full control")

    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR:")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        print("\nPossible issues:")
        print("1. Wrong Device ID, IP, or Local Key")
        print("2. Device is not responding or offline")
        print("3. Not on the same network as the device")
        print("4. Firewall blocking connection")
        print("\nTo get your device credentials, run:")
        print("  python -m tinytuya wizard")
        print("\nOr use the Tuya IoT Platform:")
        print("  https://iot.tuya.com/")


if __name__ == "__main__":
    test_arlec()
