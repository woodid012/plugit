"""
Quick test for Arlec Smart Plug using Tuya Cloud API
Tests cloud connection and device discovery
"""

import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_API_REGION

import tinytuya


def test_cloud_connection():
    """Test connection to Tuya Cloud API and discover devices"""
    ACCESS_ID = TUYA_ACCESS_ID
    ACCESS_SECRET = TUYA_ACCESS_SECRET
    REGION = TUYA_API_REGION

    print("=" * 70)
    print("Arlec/Tuya Cloud API Connection Test")
    print("=" * 70)
    print(f"\nAccess ID:  {ACCESS_ID}")
    print(f"Region:     {REGION}")
    print(f"Secret:     {'*' * len(ACCESS_SECRET)}\n")

    try:
        # Create cloud connection
        print("Connecting to Tuya Cloud API...")
        cloud = tinytuya.Cloud(
            apiRegion=REGION,
            apiKey=ACCESS_ID,
            apiSecret=ACCESS_SECRET
        )

        print("[OK] Connected to Tuya Cloud API!")

        # Discover devices
        print("\nDiscovering devices...")
        devices = cloud.getdevices()

        if not devices:
            print("\n[WARNING] No devices found!")
            print("\nCheck:")
            print("1. Your Smart Life/Tuya app account is linked to the cloud project")
            print("2. Devices are added to your app")
            print("3. Devices are online")
            return

        print(f"[OK] Found {len(devices)} device(s)!\n")

        print("=" * 70)
        print("Discovered Devices:")
        print("=" * 70)

        for i, device in enumerate(devices, 1):
            print(f"\n[{i}] {device.get('name', 'Unnamed Device')}")
            print(f"    Device ID:  {device.get('id', 'N/A')}")
            print(f"    Product:    {device.get('product_name', 'N/A')}")
            print(f"    Category:   {device.get('category', 'N/A')}")
            print(f"    Online:     {device.get('online', False)}")
            print(f"    Model:      {device.get('model', 'N/A')}")

        print("\n" + "=" * 70)

        # Test controlling the first device
        if devices:
            test_device = devices[0]
            device_id = test_device.get('id')
            device_name = test_device.get('name', 'Unknown')

            print(f"Testing control with: {device_name}")
            print("=" * 70)

            # Get status
            print("\nGetting device status...")
            status = cloud.getstatus(device_id)

            if status and 'result' in status:
                print("[OK] Device status retrieved:")
                for item in status['result']:
                    code = item.get('code', 'unknown')
                    value = item.get('value', 'N/A')
                    print(f"  {code}: {value}")
            else:
                print(f"Status response: {status}")

            # Test turning ON with correct format
            print("\nTesting control...")

            import time

            print("\n  Turning device ON...")
            on_cmd = {'commands': [{'code': 'switch_1', 'value': True}]}
            result_on = cloud.sendcommand(device_id, on_cmd)

            success = False
            if result_on.get('success', False):
                print("  [OK] Device turned ON successfully!")
                success = True
                time.sleep(2)

                # Now try turning it off
                print("\n  Turning device OFF...")
                off_cmd = {'commands': [{'code': 'switch_1', 'value': False}]}
                result_off = cloud.sendcommand(device_id, off_cmd)

                if result_off.get('success', False):
                    print("  [OK] Device turned OFF successfully!")
                else:
                    print(f"  [FAIL] Response: {result_off}")
            else:
                print(f"  [FAIL] Response: {result_on}")

        print("\n" + "=" * 70)
        if success:
            print("SUCCESS! Your Tuya Cloud API connection is working!")
            print("=" * 70)
            print("\nYou can now use arlec_cloud_controller.py for full control")
        else:
            print("PARTIAL SUCCESS - Connected but device control not working")
            print("=" * 70)
            print("\nDevice discovery works, but control commands are failing.")
            print("\nTo fix this, add API permissions in your Tuya Cloud project:")
            print("1. Go to https://iot.tuya.com/")
            print("2. Open your cloud project")
            print("3. Go to 'Service API' tab")
            print("4. Subscribe to these APIs (they're free):")
            print("   - IoT Core")
            print("   - Authorization")
            print("   - Device Status Notification")
            print("   - Smart Home Devices Management")
            print("5. Save and wait 2-3 minutes for permissions to activate")
            print("\nThen run this test again.")

    except Exception as e:
        print("\n" + "=" * 70)
        print("ERROR:")
        print("=" * 70)
        print(f"{type(e).__name__}: {e}")
        print("\nPossible issues:")
        print("1. Wrong Access ID or Access Secret")
        print("2. Wrong API region")
        print("3. Cloud project doesn't have correct permissions")
        print("4. App account not linked to cloud project")
        print("\nVerify your credentials at: https://iot.tuya.com/")


if __name__ == "__main__":
    test_cloud_connection()
