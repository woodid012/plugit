"""
Meross Device Connection Test
Tests connection to Meross smart devices (plugs, switches, etc.)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent))
from IoS_logins import MEROSS_EMAIL, MEROSS_PASSWORD

from meross_iot.http_api import MerossHttpClient
from meross_iot.manager import MerossManager


async def test_meross():
    """Test connection to Meross devices"""
    # Configuration
    EMAIL = MEROSS_EMAIL
    PASSWORD = MEROSS_PASSWORD

    print("=" * 60)
    print("Meross Device Connection Test")
    print("=" * 60)
    print(f"\nEmail: {EMAIL}")
    print(f"Password: {'*' * len(PASSWORD)}\n")

    http_api_client = None
    manager = None

    try:
        # Setup the HTTP client API (using AP region to avoid redirect)
        print("Connecting to Meross Cloud...")
        http_api_client = await MerossHttpClient.async_from_user_password(
            api_base_url="https://iotx-ap.meross.com",
            email=EMAIL,
            password=PASSWORD
        )

        # Setup and start the device manager
        print("[OK] Cloud authentication successful!")
        print("\nDiscovering Meross devices...")

        manager = MerossManager(http_client=http_api_client)
        await manager.async_init()

        # Discover devices
        await manager.async_device_discovery()
        devices = manager.find_devices()

        if not devices:
            print("\n" + "=" * 60)
            print("No Meross devices found")
            print("=" * 60)
            print("\nPossible reasons:")
            print("1. No devices are registered to this account")
            print("2. Devices are offline")
            print("3. Account credentials are incorrect")
            return

        print(f"\n[OK] Found {len(devices)} device(s)!")
        print("\n" + "=" * 60)
        print("Meross Devices Found:")
        print("=" * 60)

        for i, device in enumerate(devices, 1):
            # Handle different attribute names
            hw_ver = getattr(device, 'hwversion', getattr(device, 'hw_version', 'Unknown'))
            fw_ver = getattr(device, 'fwversion', getattr(device, 'fw_version', 'Unknown'))

            print(f"\nDevice {i}:")
            print(f"  Name:        {device.name}")
            print(f"  Type:        {device.type}")
            print(f"  Model:       {hw_ver}")
            print(f"  Firmware:    {fw_ver}")
            print(f"  Online:      {device.online_status}")
            print(f"  IP Address:  {device.internal_ip if hasattr(device, 'internal_ip') else 'N/A'}")

            # Update device status
            await device.async_update()

            # Check if it's a switch/plug
            if device.is_on() is not None:
                print(f"  Status:      {'ON' if device.is_on() else 'OFF'}")

        # Test control on first device if it's a switch
        if devices and devices[0].is_on() is not None:
            print("\n" + "=" * 60)
            print("Testing Control on First Device")
            print("=" * 60)

            device = devices[0]
            print(f"\nTesting: {device.name}")

            # Turn ON
            print("Turning device ON...")
            await device.async_turn_on()
            await asyncio.sleep(1)
            print("[OK] Device is ON")

            await asyncio.sleep(2)

            # Turn OFF
            print("\nTurning device OFF...")
            await device.async_turn_off()
            await asyncio.sleep(1)
            print("[OK] Device is OFF")

            print("\n" + "=" * 60)
            print("SUCCESS! Meross devices are working correctly!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("Device discovery successful!")
            print("=" * 60)

    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR:")
        print("=" * 60)
        print(f"{type(e).__name__}: {e}")
        print("\nPossible issues:")
        print("1. Wrong email/password credentials")
        print("2. Meross cloud service is unavailable")
        print("3. Network connection issues")
        print("4. No devices registered to this account")

    finally:
        # Cleanup
        if manager:
            manager.close()
        if http_api_client:
            await http_api_client.async_logout()


if __name__ == "__main__":
    # Run on Windows
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(test_meross())
