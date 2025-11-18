"""
Tapo P100 Controller using the 'tapo' library (v0.8.7+)
Interactive menu for controlling your Tapo P100 smart plug
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent))
from IoS_logins import TAPO_EMAIL, TAPO_PASSWORD, KNOWN_DEVICES, get_all_tapo_devices

from tapo import ApiClient


class TapoController:
    def __init__(self, ip, email, password):
        self.ip = ip
        self.email = email
        self.password = password
        self.client = None
        self.device = None

    async def connect(self):
        """Connect to the Tapo device"""
        try:
            self.client = ApiClient(self.email, self.password)
            # Try P110 first (newer model with power monitoring)
            try:
                self.device = await self.client.p110(self.ip)
            except:
                # Fall back to P100 if P110 doesn't work
                self.device = await self.client.p100(self.ip)
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    async def turn_on(self):
        """Turn the plug ON"""
        try:
            await self.device.on()
            print("[OK] Plug turned ON")
        except Exception as e:
            print(f"Error: {e}")

    async def turn_off(self):
        """Turn the plug OFF"""
        try:
            await self.device.off()
            print("[OK] Plug turned OFF")
        except Exception as e:
            print(f"Error: {e}")

    async def get_info(self):
        """Get and display device information"""
        try:
            info = await self.device.get_device_info()
            print("\n" + "=" * 60)
            print("Device Information:")
            print("=" * 60)
            print(f"Model:           {info.model}")
            print(f"Type:            {info.type}")
            print(f"Device ON:       {info.device_on}")
            print(f"Hardware Ver:    {info.hw_ver}")
            print(f"Firmware Ver:    {info.fw_ver}")
            print(f"MAC Address:     {info.mac}")
            print(f"Signal Level:    {info.signal_level}")
            print(f"RSSI:            {info.rssi} dBm")
            if hasattr(info, 'nickname'):
                print(f"Nickname:        {info.nickname}")
            print("=" * 60)
        except Exception as e:
            print(f"Error getting info: {e}")

    async def get_energy_usage(self):
        """Get power monitoring data (if supported)"""
        try:
            # Get current power (real-time)
            current_power = await self.device.get_current_power()
            if current_power and hasattr(current_power, 'current_power'):
                power_watts = float(current_power.current_power)
                voltage = 240.0  # Australian standard
                current_amps = power_watts / voltage

                print("\n" + "=" * 60)
                print("Power Monitoring Data:")
                print("=" * 60)
                print(f"Power:           {power_watts:.2f} W")
                print(f"Current:         {current_amps:.2f} A (calculated at 240V)")
                print(f"Voltage:         {voltage:.1f} V (Australian standard)")
                print("=" * 60)

            # Get historical usage data
            try:
                usage = await self.device.get_energy_usage()
                if usage:
                    print("\nHistorical Usage:")
                    print("-" * 60)
                    print(f"Today's Usage:   {usage.today_energy} Wh")
                    print(f"Today's Runtime: {usage.today_runtime} minutes")
                    print(f"This Month:      {usage.month_energy} Wh")
                    print(f"Month Runtime:   {usage.month_runtime} minutes")
                    print("=" * 60)
            except:
                pass  # Historical data not critical

        except Exception as e:
            print(f"Power monitoring not available: {e}")


async def main():
    """Main interactive menu"""
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
        print("Tapo P100 Interactive Controller")
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
    print("Tapo P100 Interactive Controller")
    print("=" * 60)
    print(f"Device: {device_name}")
    print(f"IP: {PLUG_IP}")
    print("=" * 60)

    # Create controller
    controller = TapoController(PLUG_IP, EMAIL, PASSWORD)

    # Connect
    print("\nConnecting to device...")
    if not await controller.connect():
        print("\n[ERROR] Failed to connect to the device")
        print("\nCheck:")
        print("1. IP address is correct")
        print("2. Device is powered on and connected to WiFi")
        print("3. Credentials are correct")
        return

    print("[OK] Connected successfully!\n")

    # Get initial device info
    await controller.get_info()

    # Interactive menu loop
    while True:
        print("\n" + "=" * 60)
        print("Control Menu:")
        print("=" * 60)
        print("1. Turn ON")
        print("2. Turn OFF")
        print("3. Get Device Info")
        print("4. Get Energy Usage")
        print("5. Exit")
        print("=" * 60)

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "1":
            await controller.turn_on()
        elif choice == "2":
            await controller.turn_off()
        elif choice == "3":
            await controller.get_info()
        elif choice == "4":
            await controller.get_energy_usage()
        elif choice == "5":
            print("\nExiting... Goodbye!")
            break
        else:
            print("Invalid choice, please try again")

        await asyncio.sleep(0.3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
