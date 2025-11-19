"""
Matter Device Controller
Control Matter-compatible smart plugs with energy monitoring via local Matter protocol
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import credentials
sys.path.insert(0, str(Path(__file__).parent.parent))
from IoS_logins import MATTER_DEVICES, get_all_matter_devices

# Try to import Matter libraries - support multiple options
try:
    from matter_server.client import MatterClient
    MATTER_CLIENT_AVAILABLE = True
except ImportError:
    MATTER_CLIENT_AVAILABLE = False
    try:
        # Alternative: python-matter-server
        from matter_server import MatterServer
        MATTER_CLIENT_AVAILABLE = True
    except ImportError:
        MATTER_CLIENT_AVAILABLE = False


class MatterController:
    def __init__(self, device_id, ip=None, port=5540):
        """
        Initialize Matter controller
        
        Args:
            device_id: Matter device ID or node ID
            ip: Device IP address (optional, for direct connection)
            port: Matter server port (default 5540)
        """
        self.device_id = device_id
        self.ip = ip
        self.port = port
        self.client = None
        self.device = None
        self.connected = False

    async def connect(self):
        """Connect to the Matter device"""
        try:
            if not MATTER_CLIENT_AVAILABLE:
                print("[WARNING] Matter client library not available. Install python-matter-server or matter-server")
                print("Install with: pip install python-matter-server")
                return False
            
            # Connect to Matter server (running locally or on device)
            if self.ip:
                # Direct connection to device
                server_url = f"http://{self.ip}:{self.port}"
            else:
                # Connect to local Matter server
                server_url = "http://localhost:5580"
            
            # Initialize Matter client
            # Note: Actual implementation depends on Matter library used
            # This is a template that can be adapted
            self.client = MatterClient(server_url)
            await self.client.connect()
            
            # Get device by ID
            self.device = await self.client.get_device(self.device_id)
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            # Fallback: Try alternative connection method
            try:
                return await self._connect_fallback()
            except Exception as e2:
                print(f"Fallback connection also failed: {e2}")
                return False

    async def _connect_fallback(self):
        """Fallback connection method using chip-tool or direct Matter SDK"""
        # This would use chip-tool wrapper or direct Matter SDK
        # For now, return False - to be implemented based on actual Matter library
        return False

    async def turn_on(self):
        """Turn the plug ON"""
        try:
            if not self.connected or not self.device:
                if not await self.connect():
                    raise Exception("Not connected to device")
            
            # Matter OnOff cluster - command 0x01 (On)
            await self.device.set_onoff(True)
            print("[OK] Plug turned ON")
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    async def turn_off(self):
        """Turn the plug OFF"""
        try:
            if not self.connected or not self.device:
                if not await self.connect():
                    raise Exception("Not connected to device")
            
            # Matter OnOff cluster - command 0x00 (Off)
            await self.device.set_onoff(False)
            print("[OK] Plug turned OFF")
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False

    async def get_info(self):
        """Get and display device information"""
        try:
            if not self.connected or not self.device:
                if not await self.connect():
                    raise Exception("Not connected to device")
            
            info = await self.device.get_device_info()
            print("\n" + "=" * 60)
            print("Device Information:")
            print("=" * 60)
            print(f"Device ID:       {self.device_id}")
            if self.ip:
                print(f"IP Address:      {self.ip}")
            if hasattr(info, 'vendor_name'):
                print(f"Vendor:          {info.vendor_name}")
            if hasattr(info, 'product_name'):
                print(f"Product:         {info.product_name}")
            if hasattr(info, 'serial_number'):
                print(f"Serial Number:   {info.serial_number}")
            if hasattr(info, 'software_version'):
                print(f"Firmware:        {info.software_version}")
            if hasattr(info, 'hardware_version'):
                print(f"Hardware:        {info.hardware_version}")
            print("=" * 60)
            return info
        except Exception as e:
            print(f"Error getting info: {e}")
            return None

    async def get_status(self):
        """Get device status (on/off)"""
        try:
            if not self.connected or not self.device:
                if not await self.connect():
                    return {'online': False, 'status': 'unknown'}
            
            # Read OnOff cluster attribute
            is_on = await self.device.get_onoff()
            
            return {
                'online': True,
                'status': 'on' if is_on else 'off'
            }
        except Exception as e:
            print(f"Error getting status: {e}")
            return {'online': False, 'status': 'unknown'}

    async def get_energy_usage(self):
        """Get power monitoring data (if supported)"""
        try:
            if not self.connected or not self.device:
                if not await self.connect():
                    raise Exception("Not connected to device")
            
            # Matter Electrical Measurement cluster
            # Attributes: ActivePower, RMSVoltage, RMSCurrent
            energy_data = await self.device.get_energy_measurement()
            
            if energy_data:
                power_watts = getattr(energy_data, 'active_power', getattr(energy_data, 'power', None))
                voltage = getattr(energy_data, 'rms_voltage', getattr(energy_data, 'voltage', None))
                current = getattr(energy_data, 'rms_current', getattr(energy_data, 'current', None))
                
                print("\n" + "=" * 60)
                print("Power Monitoring Data:")
                print("=" * 60)
                if power_watts is not None:
                    print(f"Power:           {power_watts:.2f} W")
                if voltage is not None:
                    print(f"Voltage:         {voltage:.1f} V")
                else:
                    print(f"Voltage:         240.0 V (assumed)")
                if current is not None:
                    print(f"Current:         {current:.2f} A")
                elif power_watts is not None:
                    # Calculate current if we have power
                    voltage_assumed = voltage if voltage else 240.0
                    current_calc = power_watts / voltage_assumed
                    print(f"Current:         {current_calc:.2f} A (calculated)")
                print("=" * 60)
                
                return {
                    'power': power_watts,
                    'voltage': voltage or 240.0,
                    'current': current or (power_watts / 240.0 if power_watts else None)
                }
            else:
                print("Power monitoring not available on this device")
                return None
                
        except Exception as e:
            print(f"Power monitoring not available: {e}")
            return None

    def disconnect(self):
        """Disconnect from device"""
        try:
            if self.client:
                asyncio.create_task(self.client.disconnect())
            self.connected = False
            self.device = None
        except Exception as e:
            print(f"Error disconnecting: {e}")


async def main():
    """Main interactive menu"""
    # Get all available Matter devices
    all_devices = get_all_matter_devices()
    
    if not all_devices:
        print("=" * 60)
        print("No Matter devices found!")
        print("=" * 60)
        print("\nAdd devices via IoS_logins.py or configure them")
        return
    
    # If only one device, use it automatically
    if len(all_devices) == 1:
        device = all_devices[0]
        DEVICE_ID = device['device_id']
        DEVICE_IP = device.get('ip')
        device_name = device.get('name', DEVICE_ID)
    else:
        # Let user choose
        print("=" * 60)
        print("Matter Device Interactive Controller")
        print("=" * 60)
        print("\nAvailable Matter Devices:")
        print("-" * 60)
        for i, device in enumerate(all_devices, 1):
            ip_str = f" ({device.get('ip', 'N/A')})" if device.get('ip') else ""
            print(f"{i}. {device.get('name', device['device_id'])}{ip_str}")
        print("-" * 60)
        
        while True:
            try:
                choice = input(f"\nSelect device (1-{len(all_devices)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(all_devices):
                    device = all_devices[idx]
                    DEVICE_ID = device['device_id']
                    DEVICE_IP = device.get('ip')
                    device_name = device.get('name', DEVICE_ID)
                    break
                else:
                    print(f"Please enter a number between 1 and {len(all_devices)}")
            except ValueError:
                print("Please enter a valid number")
    
    print("=" * 60)
    print("Matter Device Interactive Controller")
    print("=" * 60)
    print(f"Device: {device_name}")
    print(f"Device ID: {DEVICE_ID}")
    if DEVICE_IP:
        print(f"IP: {DEVICE_IP}")
    print("=" * 60)

    # Create controller
    controller = MatterController(DEVICE_ID, DEVICE_IP)

    # Connect
    print("\nConnecting to device...")
    if not await controller.connect():
        print("\n[ERROR] Failed to connect to the device")
        print("\nCheck:")
        print("1. Device ID is correct")
        print("2. Device is powered on and connected to network")
        print("3. Matter server is running (if using server mode)")
        print("4. Matter libraries are installed: pip install python-matter-server")
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
        print("5. Get Status")
        print("6. Exit")
        print("=" * 60)

        choice = input("\nEnter your choice (1-6): ").strip()

        if choice == "1":
            await controller.turn_on()
        elif choice == "2":
            await controller.turn_off()
        elif choice == "3":
            await controller.get_info()
        elif choice == "4":
            await controller.get_energy_usage()
        elif choice == "5":
            status = await controller.get_status()
            print(f"\nStatus: {status['status']} ({'Online' if status['online'] else 'Offline'})")
        elif choice == "6":
            print("\nExiting... Goodbye!")
            controller.disconnect()
            break
        else:
            print("Invalid choice, please try again")

        await asyncio.sleep(0.3)


if __name__ == "__main__":
    # Windows event loop policy
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")



