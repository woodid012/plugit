"""
Matter Device Discovery and Pairing
Discover Matter devices on the network and handle pairing/commissioning
"""

import asyncio
import socket
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Try to import Matter libraries
try:
    from matter_server.client import MatterClient
    MATTER_AVAILABLE = True
except ImportError:
    MATTER_AVAILABLE = False


def scan_network_for_matter_devices(network_range=None):
    """
    Scan network for Matter devices
    Matter devices typically use mDNS (Bonjour) for discovery
    
    Args:
        network_range: Network range to scan (e.g., "192.168.1.0/24")
                      If None, tries to auto-detect
    """
    print("=" * 60)
    print("Matter Device Discovery")
    print("=" * 60)
    print("\nScanning for Matter devices...")
    print("(Matter devices use mDNS/Bonjour for discovery)")
    
    devices_found = []
    
    try:
        # Matter devices advertise via mDNS with service type:
        # _matter._tcp.local or _matterd._tcp.local
        
        # Try to use zeroconf for mDNS discovery
        try:
            from zeroconf import ServiceBrowser, Zeroconf
            import threading
            
            class MatterListener:
                def __init__(self):
                    self.devices = []
                
                def add_service(self, zeroconf, service_type, name):
                    info = zeroconf.get_service_info(service_type, name)
                    if info:
                        addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
                        port = info.port
                        device_info = {
                            'name': name.replace('._matter._tcp.local.', ''),
                            'ip': addresses[0] if addresses else None,
                            'port': port,
                            'type': service_type
                        }
                        self.devices.append(device_info)
                        print(f"\n[FOUND] {device_info['name']}")
                        print(f"  IP: {device_info['ip']}")
                        print(f"  Port: {device_info['port']}")
            
            listener = MatterListener()
            zeroconf = Zeroconf()
            browser = ServiceBrowser(zeroconf, "_matter._tcp.local.", listener)
            
            print("\nScanning for 10 seconds...")
            print("(Make sure Matter devices are in pairing mode)")
            threading.Event().wait(10)
            
            browser.cancel()
            zeroconf.close()
            
            devices_found = listener.devices
            
        except ImportError:
            print("\n[INFO] zeroconf library not installed.")
            print("Install with: pip install zeroconf")
            print("\nFalling back to manual IP scanning...")
            
            # Fallback: Try common IPs or ask user
            return manual_ip_discovery()
    
    except Exception as e:
        print(f"\n[ERROR] Discovery failed: {e}")
        print("\nFalling back to manual IP discovery...")
        return manual_ip_discovery()
    
    if not devices_found:
        print("\n[INFO] No Matter devices found via mDNS")
        print("Trying manual IP discovery...")
        return manual_ip_discovery()
    
    return devices_found


def manual_ip_discovery():
    """Manual IP discovery - ask user or try common IPs"""
    print("\n" + "=" * 60)
    print("Manual Device Discovery")
    print("=" * 60)
    
    devices = []
    
    # Ask user for device IP
    while True:
        ip = input("\nEnter Matter device IP address (or 'done' to finish): ").strip()
        if ip.lower() == 'done':
            break
        
        if not ip:
            continue
        
        # Validate IP format
        try:
            socket.inet_aton(ip)
            
            # Try to connect and verify it's a Matter device
            name = input(f"Enter device name for {ip} (or press Enter for default): ").strip()
            if not name:
                name = f"Matter Device {ip}"
            
            devices.append({
                'name': name,
                'ip': ip,
                'port': 5540  # Default Matter port
            })
            print(f"[OK] Added {name} at {ip}")
            
        except socket.error:
            print(f"[ERROR] Invalid IP address: {ip}")
    
    return devices


async def pair_matter_device(ip, port=5540, pairing_code=None):
    """
    Pair/commission a Matter device
    
    Args:
        ip: Device IP address
        port: Device port (default 5540)
        pairing_code: Pairing code from device (QR code or manual entry)
    
    Returns:
        device_id if successful, None otherwise
    """
    print("\n" + "=" * 60)
    print("Matter Device Pairing")
    print("=" * 60)
    
    if not MATTER_AVAILABLE:
        print("\n[ERROR] Matter client library not available")
        print("Install with: pip install python-matter-server")
        return None
    
    try:
        # Connect to Matter server
        server_url = f"http://{ip}:{port}"
        client = MatterClient(server_url)
        await client.connect()
        
        # If no pairing code provided, ask user
        if not pairing_code:
            pairing_code = input("\nEnter pairing code from device (or QR code data): ").strip()
        
        if not pairing_code:
            print("[ERROR] Pairing code required")
            return None
        
        # Commission device
        print(f"\nPairing device at {ip}...")
        device_id = await client.commission_device(ip, pairing_code)
        
        if device_id:
            print(f"[OK] Device paired successfully!")
            print(f"Device ID: {device_id}")
            return device_id
        else:
            print("[ERROR] Pairing failed")
            return None
            
    except Exception as e:
        print(f"[ERROR] Pairing error: {e}")
        return None


async def discover_and_pair():
    """Main discovery and pairing workflow"""
    print("=" * 60)
    print("Matter Device Discovery and Pairing")
    print("=" * 60)
    
    # Step 1: Discover devices
    devices = scan_network_for_matter_devices()
    
    if not devices:
        print("\n[INFO] No devices found. You can manually add devices.")
        return
    
    # Step 2: Let user select device to pair
    print("\n" + "=" * 60)
    print("Select Device to Pair:")
    print("=" * 60)
    for i, device in enumerate(devices, 1):
        print(f"{i}. {device['name']} ({device.get('ip', 'N/A')})")
    print(f"{len(devices) + 1}. Skip pairing")
    
    try:
        choice = input(f"\nSelect device (1-{len(devices) + 1}): ").strip()
        idx = int(choice) - 1
        
        if 0 <= idx < len(devices):
            device = devices[idx]
            device_id = await pair_matter_device(
                device.get('ip'),
                device.get('port', 5540)
            )
            
            if device_id:
                print(f"\n[SUCCESS] Device paired! Device ID: {device_id}")
                print("\nAdd this to IoS_logins.py:")
                print(f"MATTER_DEVICES['{device['name']}'] = {{")
                print(f"    'device_id': '{device_id}',")
                print(f"    'ip': '{device.get('ip')}',")
                print(f"    'name': '{device['name']}'")
                print("}")
        else:
            print("Skipping pairing")
    
    except (ValueError, IndexError) as e:
        print(f"Invalid selection: {e}")


if __name__ == "__main__":
    # Windows event loop policy
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(discover_and_pair())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")


