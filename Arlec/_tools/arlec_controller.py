"""
Arlec Smart Plug Controller using TinyTuya
Interactive menu for controlling your Arlec smart plugs via local WiFi
"""

import sys
import time
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import ARLEC_DEVICE_ID, ARLEC_DEVICE_IP, ARLEC_LOCAL_KEY

import tinytuya


class ArlecController:
    def __init__(self, device_id, ip_address, local_key):
        """
        Initialize Arlec controller

        Args:
            device_id: Tuya device ID
            ip_address: Local IP address of the device
            local_key: Local encryption key
        """
        self.device_id = device_id
        self.ip_address = ip_address
        self.local_key = local_key
        self.device = None

    def connect(self):
        """Connect to the Arlec device"""
        try:
            self.device = tinytuya.OutletDevice(
                dev_id=self.device_id,
                address=self.ip_address,
                local_key=self.local_key,
                version=3.3  # Most Arlec devices use protocol 3.3
            )

            # Set socket timeout
            self.device.set_socketTimeout(5)

            # Test connection by getting status
            status = self.device.status()
            if status and 'dps' in status:
                print("[OK] Connected successfully!")
                return True
            else:
                print(f"[ERROR] Connection failed: {status}")
                return False

        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False

    def turn_on(self):
        """Turn the plug ON"""
        try:
            self.device.turn_on()
            time.sleep(0.5)  # Small delay to ensure command is processed
            print("[OK] Plug turned ON")
        except Exception as e:
            print(f"[ERROR] Failed to turn on: {e}")

    def turn_off(self):
        """Turn the plug OFF"""
        try:
            self.device.turn_off()
            time.sleep(0.5)  # Small delay to ensure command is processed
            print("[OK] Plug turned OFF")
        except Exception as e:
            print(f"[ERROR] Failed to turn off: {e}")

    def toggle(self):
        """Toggle the plug state"""
        try:
            status = self.get_status()
            if status and 'dps' in status:
                current_state = status['dps'].get('1', False)
                if current_state:
                    self.turn_off()
                else:
                    self.turn_on()
            else:
                print("[ERROR] Could not determine current state")
        except Exception as e:
            print(f"[ERROR] Failed to toggle: {e}")

    def get_status(self):
        """Get current device status"""
        try:
            status = self.device.status()
            return status
        except Exception as e:
            print(f"[ERROR] Failed to get status: {e}")
            return None

    def get_info(self):
        """Get and display detailed device information"""
        try:
            print("\n" + "=" * 60)
            print("Device Information:")
            print("=" * 60)

            # Get status
            status = self.get_status()

            if status and 'dps' in status:
                # DPS (Data Point) values
                dps = status['dps']

                # Common DPS points:
                # '1' = Switch state (True/False)
                # '9' = Countdown timer
                # '17' = Current (mA)
                # '18' = Power (W)
                # '19' = Voltage (V)
                # '20' = Energy (kWh)

                print(f"Device ID:       {self.device_id}")
                print(f"IP Address:      {self.ip_address}")
                print(f"Protocol:        {self.device.version}")

                if '1' in dps:
                    state = "ON" if dps['1'] else "OFF"
                    print(f"Power State:     {state}")

                if '18' in dps:
                    power_w = dps['18'] / 10  # Convert to watts
                    print(f"Current Power:   {power_w:.1f} W")

                if '19' in dps:
                    voltage_v = dps['19'] / 10  # Convert to volts
                    print(f"Voltage:         {voltage_v:.1f} V")

                if '17' in dps:
                    current_ma = dps['17']
                    print(f"Current:         {current_ma} mA")

                if '20' in dps:
                    energy_kwh = dps['20'] / 100  # Convert to kWh
                    print(f"Total Energy:    {energy_kwh:.3f} kWh")

                print("\nRaw DPS Data:")
                for key, value in dps.items():
                    print(f"  DPS {key}: {value}")

            else:
                print("Could not retrieve device status")

            print("=" * 60)

        except Exception as e:
            print(f"[ERROR] Failed to get device info: {e}")


def main():
    """Main interactive menu"""
    # Configuration - load from credentials file
    DEVICE_ID = ARLEC_DEVICE_ID
    DEVICE_IP = ARLEC_DEVICE_IP
    LOCAL_KEY = ARLEC_LOCAL_KEY

    print("=" * 60)
    print("Arlec Smart Plug Controller (via TinyTuya)")
    print("=" * 60)
    print(f"Device ID:  {DEVICE_ID}")
    print(f"Device IP:  {DEVICE_IP}")
    print("=" * 60)

    # Create controller
    controller = ArlecController(DEVICE_ID, DEVICE_IP, LOCAL_KEY)

    # Connect
    print("\nConnecting to device...")
    if not controller.connect():
        print("\n[ERROR] Failed to connect to the device")
        print("\nCheck:")
        print("1. Device ID, IP, and Local Key are correct")
        print("2. Device is powered on and connected to WiFi")
        print("3. You're on the same network as the device")
        print("4. Run 'python -m tinytuya wizard' to get device credentials")
        return

    # Get initial device info
    controller.get_info()

    # Interactive menu loop
    while True:
        print("\n" + "=" * 60)
        print("Control Menu:")
        print("=" * 60)
        print("1. Turn ON")
        print("2. Turn OFF")
        print("3. Toggle")
        print("4. Get Device Info")
        print("5. Get Status")
        print("6. Exit")
        print("=" * 60)

        choice = input("\nEnter your choice (1-6): ").strip()

        if choice == "1":
            controller.turn_on()
        elif choice == "2":
            controller.turn_off()
        elif choice == "3":
            controller.toggle()
        elif choice == "4":
            controller.get_info()
        elif choice == "5":
            status = controller.get_status()
            if status:
                print(f"\nStatus: {status}")
        elif choice == "6":
            print("\nExiting... Goodbye!")
            break
        else:
            print("[ERROR] Invalid choice, please try again")

        time.sleep(0.3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
