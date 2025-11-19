"""
Quick test for Tapo P100 using the 'tapo' library
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import TAPO_EMAIL, TAPO_PASSWORD, KNOWN_DEVICES, get_all_tapo_devices

from tapo import ApiClient


async def test_tapo():
    """Test connection to Tapo P100"""
    # Get all available Tapo devices
    all_devices = get_all_tapo_devices()
    
    if not all_devices:
        print("=" * 60)
        print("No Tapo devices found!")
        print("=" * 60)
        print("\nAdd devices via the web interface or update IoS_logins.py")
        return
    
    # If only one device, use it automatically
    if len(all_devices) == 1:
        device = all_devices[0]
        PLUG_IP = device['ip']
        EMAIL = device['email']
        PASSWORD = device['password']
        device_name = device['name']
    else:
        # Let user choose
        print("=" * 60)
        print("Tapo P100 Connection Test")
        print("=" * 60)
        print("\nAvailable Tapo Devices:")
        print("-" * 60)
        for i, device in enumerate(all_devices, 1):
            print(f"{i}. {device['name']} ({device['ip']})")
        print("-" * 60)
        
        while True:
            try:
                choice = input(f"\nSelect device (1-{len(all_devices)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(all_devices):
                    device = all_devices[idx]
                    PLUG_IP = device['ip']
                    EMAIL = device['email']
                    PASSWORD = device['password']
                    device_name = device['name']
                    break
                else:
                    print(f"Please enter a number between 1 and {len(all_devices)}")
            except ValueError:
                print("Please enter a valid number")

    print("=" * 60)
    print("Tapo P100 Connection Test")
    print("=" * 60)
    print(f"\nDevice: {device_name}")
    print(f"Connecting to {PLUG_IP}...")
    print(f"Email: {EMAIL}")
    print(f"Password: {'*' * len(PASSWORD)}\n")

    try:
        # Create API client
        client = ApiClient(EMAIL, PASSWORD)

        # Connect to the device - try P110 first (newer model with power monitoring)
        try:
            device = await client.p110(PLUG_IP)
            print("[OK] Connected successfully! (P110 mode)")
        except:
            # Fall back to P100 if P110 doesn't work
            device = await client.p100(PLUG_IP)
            print("[OK] Connected successfully! (P100 mode)")

        # Get device info
        print("\nGetting device information...")
        device_info = await device.get_device_info()

        print("\n" + "=" * 60)
        print("Device Information:")
        print("=" * 60)
        print(f"Device Type: {device_info.type}")
        print(f"Model: {device_info.model}")
        print(f"Hardware Version: {device_info.hw_ver}")
        print(f"Firmware Version: {device_info.fw_ver}")
        print(f"Device ON: {device_info.device_on}")
        print(f"MAC Address: {device_info.mac}")
        print(f"Signal Level: {device_info.signal_level}")
        print(f"RSSI: {device_info.rssi}")
        if hasattr(device_info, 'nickname'):
            print(f"Nickname: {device_info.nickname}")
        print("=" * 60)

        # Test power monitoring (if available)
        print("\nTesting power monitoring...")
        try:
            current_power = await device.get_current_power()
            if current_power and hasattr(current_power, 'current_power'):
                power_watts = float(current_power.current_power)
                voltage = 240.0  # Australian standard
                current_amps = power_watts / voltage if power_watts > 0 else 0.0

                print("\n" + "=" * 60)
                print("Power Monitoring Data:")
                print("=" * 60)
                print(f"Power: {power_watts:.2f} W")
                print(f"Current: {current_amps:.2f} A (calculated at 240V)")
                print(f"Voltage: {voltage:.1f} V (Australian standard)")
                print("=" * 60)
            else:
                print("[INFO] Power monitoring not available (device may be P100)")
        except Exception as e:
            print(f"[INFO] Power monitoring not available: {e}")

        # Test turning ON
        print("\n Testing control...")
        print("Turning plug ON...")
        await device.on()
        print("[OK] Plug is ON")

        await asyncio.sleep(2)

        # Test turning OFF
        print("\nTurning plug OFF...")
        await device.off()
        print("[OK] Plug is OFF")

        print("\n" + "=" * 60)
        print("SUCCESS! Your Tapo P100 is working correctly!")
        print("=" * 60)
        print("\nYou can now use tapo_controller.py for full control")

    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR:")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        print("\nPossible issues:")
        print("1. Wrong IP address")
        print("2. Wrong email/password credentials")
        print("3. Device is not responding")
        print("4. Firewall blocking connection")


if __name__ == "__main__":
    asyncio.run(test_tapo())

