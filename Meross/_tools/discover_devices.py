"""
Meross Device Discovery
Discovers and lists all Meross devices on your account
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import MEROSS_EMAIL, MEROSS_PASSWORD

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager


async def discover_meross_devices():
    """Discover all Meross devices"""
    # Configuration
    EMAIL = MEROSS_EMAIL
    PASSWORD = MEROSS_PASSWORD

    print("=" * 60)
    print("Meross Device Discovery")
    print("=" * 60)
    print(f"\nEmail: {EMAIL}")
    print(f"Password: {'*' * len(PASSWORD)}\n")

    http_api_client = None
    manager = None

    try:
        # Connect to Meross Cloud (using AP region to avoid redirect)
        print("Connecting to Meross Cloud...")
        http_api_client = await MerossHttpClient.async_from_user_password(
            api_base_url="https://iotx-ap.meross.com",
            email=EMAIL,
            password=PASSWORD
        )

        print("[OK] Authentication successful!")

        # Setup device manager
        print("Discovering devices...")
        manager = MerossManager(http_client=http_api_client)
        await manager.async_init()

        # Discover devices
        await manager.async_device_discovery()
        devices = manager.find_devices()

        if not devices:
            print("\n" + "=" * 60)
            print("No Meross devices found on your account")
            print("=" * 60)
            print("\nMake sure you have:")
            print("1. Registered devices in the Meross app")
            print("2. Devices are powered on")
            print("3. Correct account credentials")
            return

        print(f"\n[OK] Found {len(devices)} device(s)!")
        print("\n" + "=" * 70)
        print("Meross Devices on Your Account:")
        print("=" * 70)

        for i, device in enumerate(devices, 1):
            # Update device to get latest status
            await device.async_update()

            print(f"\nDevice #{i}")
            print("-" * 70)
            print(f"  Name:            {device.name}")
            print(f"  Type:            {device.type}")

            # Handle different attribute names across device types
            hw_ver = getattr(device, 'hwversion', getattr(device, 'hw_version', 'Unknown'))
            fw_ver = getattr(device, 'fwversion', getattr(device, 'fw_version', 'Unknown'))

            print(f"  Model/Hardware:  {hw_ver}")
            print(f"  Firmware:        {fw_ver}")
            print(f"  Online:          {device.online_status}")
            print(f"  UUID:            {device.uuid}")

            # Show IP address if available
            if hasattr(device, 'internal_ip') and device.internal_ip:
                print(f"  Local IP:        {device.internal_ip}")

            # Show power status for switches/plugs
            if device.is_on() is not None:
                status = "ON" if device.is_on() else "OFF"
                print(f"  Power Status:    {status}")

            # Show channels for multi-channel devices
            if hasattr(device, 'get_channels'):
                try:
                    channels = device.get_channels()
                    if len(channels) > 1:
                        print(f"  Channels:        {len(channels)}")
                        for ch_idx, channel in enumerate(channels):
                            ch_status = "ON" if channel.is_on else "OFF"
                            print(f"    Channel {ch_idx}: {ch_status}")
                except:
                    pass

            # Show abilities/capabilities
            try:
                abilities = device.get_abilities()
                if abilities:
                    print(f"  Capabilities:    {', '.join(abilities)}")
            except:
                pass

        print("\n" + "=" * 70)
        print("Device Summary:")
        print("=" * 70)

        # Count device types
        device_types = {}
        online_count = 0

        for device in devices:
            dtype = device.type
            device_types[dtype] = device_types.get(dtype, 0) + 1
            if device.online_status:
                online_count += 1

        print(f"Total Devices:   {len(devices)}")
        print(f"Online:          {online_count}")
        print(f"Offline:         {len(devices) - online_count}")
        print(f"\nDevice Types:")
        for dtype, count in device_types.items():
            print(f"  {dtype}: {count}")

        print("\n" + "=" * 70)
        print("To control these devices, run:")
        print("  python meross_controller.py")
        print("=" * 70)

    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR:")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        print("\nPossible issues:")
        print("1. Incorrect email/password")
        print("2. No internet connection")
        print("3. Meross cloud service unavailable")

    finally:
        # Cleanup
        if manager:
            manager.close()
        if http_api_client:
            await http_api_client.async_logout()


if __name__ == "__main__":
    # Windows event loop policy
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(discover_meross_devices())

