"""
Simple Arlec/Tuya Device Scanner
Scans your local network for Tuya-based devices (like Arlec smart plugs)
"""

import tinytuya
import json


def scan_devices():
    """Scan the network for Tuya devices"""
    print("=" * 70)
    print("Arlec/Tuya Device Scanner")
    print("=" * 70)
    print("\nScanning your network for Tuya-based devices...")
    print("This may take 10-20 seconds...\n")

    # Scan for devices
    devices = tinytuya.deviceScan(verbose=False, maxretry=3)

    if not devices:
        print("=" * 70)
        print("No devices found!")
        print("=" * 70)
        print("\nPossible reasons:")
        print("1. Devices are not on the same network")
        print("2. Devices are in sleep mode")
        print("3. Firewall is blocking UDP broadcasts")
        print("4. Devices need to be reset/re-paired")
        print("\nTry:")
        print("- Make sure your Arlec device is plugged in and connected to WiFi")
        print("- Check your router's connected devices list")
        print("- Ensure your computer and device are on the same network")
        return

    print("=" * 70)
    print(f"Found {len(devices)} device(s)!")
    print("=" * 70)

    for i, (device_id, device_info) in enumerate(devices.items(), 1):
        print(f"\n{'='*70}")
        print(f"Device #{i}")
        print('='*70)
        print(f"Device ID:  {device_id}")
        print(f"IP Address: {device_info.get('ip', 'Unknown')}")
        print(f"Version:    {device_info.get('version', 'Unknown')}")

        # Product key might give us a hint about the device type
        if 'productKey' in device_info:
            print(f"Product:    {device_info['productKey']}")

        # Show all available info
        print("\nFull device info:")
        for key, value in device_info.items():
            if key not in ['ip', 'version', 'productKey']:
                print(f"  {key}: {value}")

    # Save to file
    print("\n" + "=" * 70)
    print("Saving scan results...")
    print("=" * 70)

    filename = "devices.json"
    with open(filename, 'w') as f:
        json.dump(devices, f, indent=2)

    print(f"\nScan results saved to: {filename}")

    print("\n" + "=" * 70)
    print("IMPORTANT: Getting the Local Key")
    print("=" * 70)
    print("\nThe scanner found your device's IP and ID, but you still need")
    print("the LOCAL KEY to connect. Here are your options:\n")

    print("Option 1: Use TinyTuya Wizard (Most Reliable)")
    print("-" * 70)
    print("1. Create a Tuya IoT account at https://iot.tuya.com/")
    print("2. Create a Cloud Project and link your Smart Life app")
    print("3. Run: python -m tinytuya wizard")
    print("4. Follow the prompts with your API credentials")
    print("5. The wizard will get your Local Keys automatically\n")

    print("Option 2: Use TuyAPI Device Discovery (Easier)")
    print("-" * 70)
    print("There are browser-based tools that can extract the Local Key:")
    print("- Search for 'Tuya Local Key extractor'")
    print("- Use browser developer tools on the Smart Life web app")
    print("- Some Android apps can show the Local Key\n")

    print("Option 3: Manual Network Capture (Advanced)")
    print("-" * 70)
    print("Use Wireshark or tcpdump to capture the initial handshake")
    print("when the device connects to WiFi. The Local Key is transmitted")
    print("during initial setup.\n")

    print("=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print("\n1. Copy the Device ID and IP Address from above")
    print("2. Get the Local Key using one of the methods above")
    print("3. Update IoS_logins.py with these credentials:")
    print(f"   ARLEC_DEVICE_ID = \"{list(devices.keys())[0] if devices else 'your_device_id'}\"")
    print(f"   ARLEC_DEVICE_IP = \"{list(devices.values())[0].get('ip', '192.168.1.xxx') if devices else '192.168.1.xxx'}\"")
    print(f"   ARLEC_LOCAL_KEY = \"your_local_key_here\"")
    print("\n4. Run: python arlec_test.py")
    print("=" * 70)


if __name__ == "__main__":
    try:
        scan_devices()
    except KeyboardInterrupt:
        print("\n\nScan interrupted by user.")
    except Exception as e:
        print(f"\nError during scan: {e}")
        print("\nMake sure:")
        print("1. You're connected to the same WiFi network as your devices")
        print("2. Your firewall allows UDP broadcasts on port 6666-6668")
