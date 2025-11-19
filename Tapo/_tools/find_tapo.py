"""
Tapo P100 IP Address Finder
Helps you locate your Tapo P100 smart plug on your local network
"""

import socket
import ipaddress
import concurrent.futures
from PyP100 import PyP100
import sys


def get_local_ip():
    """Get the local IP address of this computer"""
    try:
        # Create a socket to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return None


def get_network_range(ip_address):
    """Get the network range from an IP address"""
    try:
        # Assume /24 subnet (255.255.255.0)
        network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
        return network
    except Exception:
        return None


def check_tapo_device(ip, email, password):
    """
    Try to connect to a potential Tapo device
    Returns device info if successful, None otherwise
    """
    try:
        # Try to connect with a short timeout
        p100 = PyP100.P100(ip, email, password)
        p100.handshake()
        p100.login()
        info = p100.getDeviceInfo()

        # Check if it's a Tapo device
        if info and ('model' in info or 'type' in info):
            return {
                'ip': ip,
                'model': info.get('model', 'Unknown'),
                'type': info.get('type', 'Unknown'),
                'device_on': info.get('device_on', 'Unknown'),
                'mac': info.get('mac', 'Unknown'),
                'nickname': info.get('nickname', 'Unknown')
            }
    except Exception:
        pass

    return None


def is_port_open(ip, port=80, timeout=0.5):
    """Check if a port is open on an IP address"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def scan_network_for_tapo(email, password):
    """Scan the local network for Tapo devices"""
    print("=" * 60)
    print("Tapo P100 IP Address Finder")
    print("=" * 60)

    # Get local IP and network range
    local_ip = get_local_ip()
    if not local_ip:
        print("Error: Could not determine your local IP address")
        return []

    print(f"\nYour computer's IP: {local_ip}")

    network = get_network_range(local_ip)
    if not network:
        print("Error: Could not determine network range")
        return []

    print(f"Scanning network: {network}")
    print("\nThis may take a few minutes...")
    print("Scanning for devices with open ports...\n")

    # First, quickly scan for devices with port 80 open
    potential_devices = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(is_port_open, str(ip)): str(ip)
                  for ip in network.hosts()}

        for future in concurrent.futures.as_completed(futures):
            ip = futures[future]
            try:
                if future.result():
                    potential_devices.append(ip)
                    print(f"Found device at: {ip}")
            except Exception:
                pass

    if not potential_devices:
        print("\nNo devices found with open port 80")
        print("Your Tapo device might be offline or on a different network")
        return []

    print(f"\n\nFound {len(potential_devices)} potential device(s)")
    print("Checking which ones are Tapo devices...\n")

    # Now check which ones are Tapo devices
    tapo_devices = []
    for ip in potential_devices:
        print(f"Checking {ip}...", end=" ")
        device_info = check_tapo_device(ip, email, password)
        if device_info:
            tapo_devices.append(device_info)
            print(f"✓ TAPO DEVICE FOUND!")
        else:
            print("not a Tapo device")

    return tapo_devices


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("Tapo P100 IP Address Finder")
    print("=" * 60)

    # Credentials
    EMAIL = "i.am.woods@gmail.com"
    PASSWORD = "Ch1cken1"

    print("\nUsing credentials:")
    print(f"Email: {EMAIL}")
    print(f"Password: {'*' * len(PASSWORD)}")

    print("\nChoose a method to find your Tapo P100:")
    print("\n1. Automatic Network Scan (scans your local network)")
    print("2. Manual IP Entry (if you already know the IP)")
    print("3. Show manual methods (router/app instructions)")
    print("4. Exit")

    choice = input("\nEnter your choice (1-4): ").strip()

    if choice == "1":
        print("\nStarting network scan...")
        tapo_devices = scan_network_for_tapo(EMAIL, PASSWORD)

        if tapo_devices:
            print("\n" + "=" * 60)
            print(f"Found {len(tapo_devices)} Tapo device(s)!")
            print("=" * 60)

            for i, device in enumerate(tapo_devices, 1):
                print(f"\nDevice {i}:")
                print(f"  IP Address: {device['ip']}")
                print(f"  Model: {device['model']}")
                print(f"  Type: {device['type']}")
                print(f"  Status: {'ON' if device['device_on'] else 'OFF'}")
                print(f"  MAC Address: {device['mac']}")
                print(f"  Nickname: {device['nickname']}")

            print("\n" + "=" * 60)
            print("Use the IP address shown above in the control scripts!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("No Tapo devices found on your network")
            print("=" * 60)
            print("\nPossible reasons:")
            print("1. The plug is not connected to WiFi")
            print("2. The plug is on a different network")
            print("3. Your credentials are incorrect")
            print("4. Firewall is blocking the scan")
            print("\nTry using the Tapo app to verify the device is online")

    elif choice == "2":
        test_ip = input("\nEnter the IP address to test: ").strip()
        print(f"\nChecking {test_ip}...")

        device_info = check_tapo_device(test_ip, EMAIL, PASSWORD)
        if device_info:
            print("\n✓ This is a Tapo device!")
            print(f"  Model: {device_info['model']}")
            print(f"  Type: {device_info['type']}")
            print(f"  Status: {'ON' if device_info['device_on'] else 'OFF'}")
            print(f"  MAC Address: {device_info['mac']}")
        else:
            print("\n✗ Could not connect to a Tapo device at this IP")
            print("Check the IP address and try again")

    elif choice == "3":
        print("\n" + "=" * 60)
        print("Manual Methods to Find Your Tapo P100 IP Address")
        print("=" * 60)

        print("\nMethod 1: Using the Tapo App")
        print("-" * 40)
        print("1. Open the Tapo app on your phone")
        print("2. Tap on your P100 device")
        print("3. Tap the gear icon (Settings) in the top right")
        print("4. Tap 'Device Info'")
        print("5. Look for 'IP Address' or 'MAC Address'")

        print("\nMethod 2: Using Your Router")
        print("-" * 40)
        print("1. Log into your router's admin panel")
        print("   (Usually at 192.168.1.1 or 192.168.0.1)")
        print("2. Find the 'Connected Devices' or 'DHCP Clients' page")
        print("3. Look for a device named 'Tapo_Plug' or similar")
        print("4. Note the IP address next to it")

        print("\nMethod 3: Windows Command Prompt")
        print("-" * 40)
        print("1. Open Command Prompt (cmd)")
        print("2. Type: arp -a")
        print("3. Look for devices in your IP range")
        print("4. Cross-reference MAC addresses with your router")

        print("\nMethod 4: Advanced IP Scanner (Windows)")
        print("-" * 40)
        print("1. Download 'Advanced IP Scanner' (free)")
        print("2. Scan your network")
        print("3. Look for TP-Link devices")

        print("\n" + "=" * 60)

    elif choice == "4":
        print("Exiting...")
        sys.exit(0)

    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()

