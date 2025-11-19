"""
Arlec Smart Plug Controller using Tuya Cloud API
Control your Arlec devices via cloud (no local IP needed!)
"""

import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_API_REGION

import tinytuya


class ArlecCloudController:
    def __init__(self, access_id, access_secret, region="us"):
        """
        Initialize Arlec Cloud Controller

        Args:
            access_id: Tuya API Access ID / Client ID
            access_secret: Tuya API Access Secret / Client Secret
            region: API region (us, eu, cn, in)
        """
        self.access_id = access_id
        self.access_secret = access_secret
        self.region = region
        self.cloud = None
        self.devices = []

    def connect(self):
        """Connect to Tuya Cloud API"""
        try:
            # Create cloud connection
            self.cloud = tinytuya.Cloud(
                apiRegion=self.region,
                apiKey=self.access_id,
                apiSecret=self.access_secret
            )

            print("[OK] Connected to Tuya Cloud API")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to connect to cloud: {e}")
            return False

    def discover_devices(self):
        """Discover all devices linked to your account"""
        try:
            # Get device list
            self.devices = self.cloud.getdevices()

            if not self.devices:
                print("[WARNING] No devices found")
                return []

            print(f"[OK] Found {len(self.devices)} device(s)")
            return self.devices

        except Exception as e:
            print(f"[ERROR] Failed to discover devices: {e}")
            return []

    def list_devices(self):
        """List all discovered devices"""
        if not self.devices:
            print("No devices available. Run discover_devices() first.")
            return

        print("\n" + "=" * 70)
        print("Available Devices:")
        print("=" * 70)

        for i, device in enumerate(self.devices, 1):
            print(f"\n[{i}] {device.get('name', 'Unnamed Device')}")
            print(f"    Device ID:  {device.get('id', 'N/A')}")
            print(f"    Product:    {device.get('product_name', 'N/A')}")
            print(f"    Online:     {device.get('online', 'N/A')}")
            print(f"    Category:   {device.get('category', 'N/A')}")

        print("=" * 70)

    def get_device_by_name(self, name):
        """Get device by name"""
        for device in self.devices:
            if name.lower() in device.get('name', '').lower():
                return device
        return None

    def get_device_by_index(self, index):
        """Get device by index (1-based)"""
        if 0 < index <= len(self.devices):
            return self.devices[index - 1]
        return None

    def get_device_status(self, device_id):
        """Get current status of a device"""
        try:
            status = self.cloud.getstatus(device_id)
            return status

        except Exception as e:
            print(f"[ERROR] Failed to get status: {e}")
            return None

    def turn_on(self, device_id):
        """Turn device ON"""
        try:
            # Use correct Tuya Cloud API format
            result = self.cloud.sendcommand(
                device_id,
                {'commands': [{'code': 'switch_1', 'value': True}]}
            )

            if result.get('success', False):
                print("[OK] Device turned ON")
                return True
            else:
                print(f"[ERROR] Failed to turn on: {result}")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to turn on: {e}")
            return False

    def turn_off(self, device_id):
        """Turn device OFF"""
        try:
            # Use correct Tuya Cloud API format
            result = self.cloud.sendcommand(
                device_id,
                {'commands': [{'code': 'switch_1', 'value': False}]}
            )

            if result.get('success', False):
                print("[OK] Device turned OFF")
                return True
            else:
                print(f"[ERROR] Failed to turn off: {result}")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to turn off: {e}")
            return False

    def toggle(self, device_id):
        """Toggle device state"""
        try:
            # Get current status
            status = self.get_device_status(device_id)

            if not status:
                print("[ERROR] Could not get device status")
                return False

            # Find the switch status
            current_state = False
            if 'result' in status:
                for item in status['result']:
                    if item.get('code') == 'switch_1':
                        current_state = item.get('value', False)
                        break

            # Toggle
            if current_state:
                return self.turn_off(device_id)
            else:
                return self.turn_on(device_id)

        except Exception as e:
            print(f"[ERROR] Failed to toggle: {e}")
            return False

    def get_device_info(self, device_id):
        """Get detailed device information"""
        try:
            # Find device in our list
            device = None
            for dev in self.devices:
                if dev.get('id') == device_id:
                    device = dev
                    break

            if not device:
                print("[ERROR] Device not found")
                return

            print("\n" + "=" * 70)
            print("Device Information:")
            print("=" * 70)
            print(f"Name:           {device.get('name', 'N/A')}")
            print(f"Device ID:      {device.get('id', 'N/A')}")
            print(f"Product:        {device.get('product_name', 'N/A')}")
            print(f"Category:       {device.get('category', 'N/A')}")
            print(f"Online:         {device.get('online', 'N/A')}")
            print(f"Model:          {device.get('model', 'N/A')}")
            print(f"UUID:           {device.get('uuid', 'N/A')}")

            # Get current status
            status = self.get_device_status(device_id)
            if status and 'result' in status:
                print("\nCurrent Status:")
                for item in status['result']:
                    code = item.get('code', 'unknown')
                    value = item.get('value', 'N/A')
                    print(f"  {code}: {value}")

            print("=" * 70)

        except Exception as e:
            print(f"[ERROR] Failed to get device info: {e}")


def main():
    """Main interactive menu"""
    # Configuration
    ACCESS_ID = TUYA_ACCESS_ID
    ACCESS_SECRET = TUYA_ACCESS_SECRET
    REGION = TUYA_API_REGION

    print("=" * 70)
    print("Arlec Smart Plug Cloud Controller (via Tuya Cloud API)")
    print("=" * 70)
    print(f"Region: {REGION}")
    print("=" * 70)

    # Create controller
    controller = ArlecCloudController(ACCESS_ID, ACCESS_SECRET, REGION)

    # Connect to cloud
    print("\nConnecting to Tuya Cloud API...")
    if not controller.connect():
        print("\n[ERROR] Failed to connect to Tuya Cloud API")
        print("\nCheck:")
        print("1. Access ID and Secret are correct")
        print("2. API region is correct (us, eu, cn, in)")
        print("3. Your Tuya Cloud project has correct permissions")
        print("\nGet credentials from: https://iot.tuya.com/")
        return

    # Discover devices
    print("\nDiscovering devices...")
    devices = controller.discover_devices()

    if not devices:
        print("\n[ERROR] No devices found")
        print("\nCheck:")
        print("1. Devices are added to your Smart Life/Tuya app")
        print("2. Your app account is linked to the Tuya Cloud project")
        print("3. Devices are online and connected to WiFi")
        return

    # Show devices
    controller.list_devices()

    # Select device
    print("\n" + "=" * 70)
    device_num = input("Enter device number to control (or 'q' to quit): ").strip()

    if device_num.lower() == 'q':
        print("Exiting...")
        return

    try:
        device_index = int(device_num)
        selected_device = controller.get_device_by_index(device_index)

        if not selected_device:
            print("[ERROR] Invalid device number")
            return

        device_id = selected_device.get('id')
        device_name = selected_device.get('name', 'Unknown')

        print(f"\nSelected: {device_name}")
        print("=" * 70)

        # Show initial info
        controller.get_device_info(device_id)

        # Interactive menu loop
        while True:
            print("\n" + "=" * 70)
            print("Control Menu:")
            print("=" * 70)
            print("1. Turn ON")
            print("2. Turn OFF")
            print("3. Toggle")
            print("4. Get Device Info")
            print("5. Get Status")
            print("6. Select Different Device")
            print("7. Exit")
            print("=" * 70)

            choice = input("\nEnter your choice (1-7): ").strip()

            if choice == "1":
                controller.turn_on(device_id)
            elif choice == "2":
                controller.turn_off(device_id)
            elif choice == "3":
                controller.toggle(device_id)
            elif choice == "4":
                controller.get_device_info(device_id)
            elif choice == "5":
                status = controller.get_device_status(device_id)
                if status:
                    print(f"\nStatus: {status}")
            elif choice == "6":
                controller.list_devices()
                device_num = input("\nEnter device number: ").strip()
                device_index = int(device_num)
                selected_device = controller.get_device_by_index(device_index)
                if selected_device:
                    device_id = selected_device.get('id')
                    device_name = selected_device.get('name', 'Unknown')
                    print(f"\nSelected: {device_name}")
                    controller.get_device_info(device_id)
                else:
                    print("[ERROR] Invalid device number")
            elif choice == "7":
                print("\nExiting... Goodbye!")
                break
            else:
                print("[ERROR] Invalid choice, please try again")

    except ValueError:
        print("[ERROR] Invalid input")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
