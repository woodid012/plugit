"""
Meross Device Interactive Controller
Control your Meross smart devices (plugs, switches, bulbs, etc.)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent))
from IoS_logins import MEROSS_EMAIL, MEROSS_PASSWORD

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager


class MerossController:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.http_client = None
        self.manager = None
        self.devices = []

    async def connect(self):
        """Connect to Meross cloud and discover devices"""
        try:
            # Setup HTTP client (using AP region to avoid redirect)
            self.http_client = await MerossHttpClient.async_from_user_password(
                api_base_url="https://iotx-ap.meross.com",
                email=self.email,
                password=self.password
            )

            # Setup device manager
            self.manager = MerossManager(http_client=self.http_client)
            await self.manager.async_init()

            # Discover devices
            await self.manager.async_device_discovery()
            self.devices = self.manager.find_devices()

            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    async def list_devices(self):
        """List all discovered devices"""
        if not self.devices:
            print("\nNo devices found")
            return

        print("\n" + "=" * 60)
        print("Your Meross Devices:")
        print("=" * 60)

        for i, device in enumerate(self.devices, 1):
            await device.async_update()

            # Handle different attribute names
            hw_ver = getattr(device, 'hwversion', getattr(device, 'hw_version', 'Unknown'))
            fw_ver = getattr(device, 'fwversion', getattr(device, 'fw_version', 'Unknown'))

            print(f"\n[{i}] {device.name}")
            print(f"    Type:        {device.type}")
            print(f"    Model:       {hw_ver}")
            print(f"    Firmware:    {fw_ver}")
            print(f"    Online:      {device.online_status}")

            if device.is_on() is not None:
                print(f"    Status:      {'ON' if device.is_on() else 'OFF'}")

        print("=" * 60)

    async def turn_on(self, device_index):
        """Turn on a specific device"""
        if 0 <= device_index < len(self.devices):
            device = self.devices[device_index]
            try:
                await device.async_turn_on()
                print(f"[OK] {device.name} turned ON")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("Invalid device number")

    async def turn_off(self, device_index):
        """Turn off a specific device"""
        if 0 <= device_index < len(self.devices):
            device = self.devices[device_index]
            try:
                await device.async_turn_off()
                print(f"[OK] {device.name} turned OFF")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("Invalid device number")

    async def toggle(self, device_index):
        """Toggle a device on/off"""
        if 0 <= device_index < len(self.devices):
            device = self.devices[device_index]
            try:
                await device.async_update()
                if device.is_on():
                    await device.async_turn_off()
                    print(f"[OK] {device.name} turned OFF")
                else:
                    await device.async_turn_on()
                    print(f"[OK] {device.name} turned ON")
            except Exception as e:
                print(f"Error: {e}")
        else:
            print("Invalid device number")

    async def get_device_info(self, device_index):
        """Get detailed info for a specific device"""
        if 0 <= device_index < len(self.devices):
            device = self.devices[device_index]
            await device.async_update()

            # Handle different attribute names
            hw_ver = getattr(device, 'hwversion', getattr(device, 'hw_version', 'Unknown'))
            fw_ver = getattr(device, 'fwversion', getattr(device, 'fw_version', 'Unknown'))

            print("\n" + "=" * 60)
            print(f"Device Information: {device.name}")
            print("=" * 60)
            print(f"Type:            {device.type}")
            print(f"Model:           {hw_ver}")
            print(f"Firmware:        {fw_ver}")
            print(f"Online Status:   {device.online_status}")
            print(f"UUID:            {device.uuid}")

            if hasattr(device, 'internal_ip'):
                print(f"IP Address:      {device.internal_ip}")

            if device.is_on() is not None:
                print(f"Power Status:    {'ON' if device.is_on() else 'OFF'}")

            # Additional capabilities
            abilities = device.get_abilities()
            if abilities:
                print(f"\nCapabilities:")
                for ability in abilities:
                    print(f"  - {ability}")

            print("=" * 60)
        else:
            print("Invalid device number")

    def cleanup(self):
        """Cleanup resources"""
        if self.manager:
            self.manager.close()


async def main():
    """Main interactive menu"""
    # Configuration
    EMAIL = MEROSS_EMAIL
    PASSWORD = MEROSS_PASSWORD

    print("=" * 60)
    print("Meross Interactive Controller")
    print("=" * 60)

    # Create controller
    controller = MerossController(EMAIL, PASSWORD)

    # Connect
    print("\nConnecting to Meross Cloud...")
    if not await controller.connect():
        print("\n[ERROR] Failed to connect")
        print("\nCheck:")
        print("1. Email and password are correct")
        print("2. Internet connection is working")
        print("3. Meross cloud service is available")
        return

    print("[OK] Connected successfully!")

    if not controller.devices:
        print("\n[ERROR] No devices found on your account")
        print("Make sure you have Meross devices registered in the Meross app")
        controller.cleanup()
        return

    print(f"[OK] Found {len(controller.devices)} device(s)")

    # Show initial device list
    await controller.list_devices()

    # Interactive menu loop
    try:
        while True:
            print("\n" + "=" * 60)
            print("Control Menu:")
            print("=" * 60)
            print("1. List All Devices")
            print("2. Turn ON a Device")
            print("3. Turn OFF a Device")
            print("4. Toggle Device")
            print("5. Get Device Details")
            print("6. Refresh Device Status")
            print("7. Exit")
            print("=" * 60)

            choice = input("\nEnter your choice (1-7): ").strip()

            if choice == "1":
                await controller.list_devices()

            elif choice in ["2", "3", "4", "5"]:
                device_num = input(f"Enter device number (1-{len(controller.devices)}): ").strip()
                try:
                    device_index = int(device_num) - 1

                    if choice == "2":
                        await controller.turn_on(device_index)
                    elif choice == "3":
                        await controller.turn_off(device_index)
                    elif choice == "4":
                        await controller.toggle(device_index)
                    elif choice == "5":
                        await controller.get_device_info(device_index)

                except ValueError:
                    print("Invalid number")

            elif choice == "6":
                print("Refreshing device status...")
                await controller.manager.async_device_discovery()
                controller.devices = controller.manager.find_devices()
                await controller.list_devices()

            elif choice == "7":
                print("\nExiting... Goodbye!")
                break

            else:
                print("Invalid choice, please try again")

            await asyncio.sleep(0.3)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    finally:
        # Cleanup
        controller.cleanup()
        if controller.http_client:
            await controller.http_client.async_logout()


if __name__ == "__main__":
    # Windows event loop policy
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
