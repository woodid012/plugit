"""
Automatic Tapo P100 Network Scanner
Automatically scans your network for Tapo devices
"""

import socket
import ipaddress
import concurrent.futures
from PyP100 import PyP100


def get_local_ip():
    """Get the local IP address of this computer"""
    try:
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
        network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
        return network
    except Exception:
        return None


def check_tapo_device(ip, email, password):
    """Try to connect to a potential Tapo device"""
    try:
        p100 = PyP100.P100(ip, email, password)
        p100.handshake()
        p100.login()
        info = p100.getDeviceInfo()

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


def main():
    """Main function - automatically scans network"""
    EMAIL = "i.am.woods@gmail.com"
    PASSWORD = "Ch1cken1"

    print("=" * 60)
    print("Automatic Tapo P100 Network Scanner")
    print("=" * 60)

    # Get local IP
    local_ip = get_local_ip()
    if not local_ip:
        print("\nError: Could not determine your local IP address")
        print("Make sure you're connected to your WiFi network")
        return

    print(f"\nYour computer's IP: {local_ip}")

    # Get network range
    network = get_network_range(local_ip)
    if not network:
        print("Error: Could not determine network range")
        return

    print(f"Scanning network: {network}")
    print("\nStep 1: Scanning for devices with open ports...")
    print("This may take 1-2 minutes...\n")

    # Scan for devices with port 80 open
    potential_devices = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(is_port_open, str(ip)): str(ip)
                  for ip in network.hosts()}

        completed = 0
        total = len(futures)
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            if completed % 20 == 0:
                print(f"Progress: {completed}/{total} IPs checked...")

            ip = futures[future]
            try:
                if future.result():
                    potential_devices.append(ip)
                    print(f"✓ Found device at: {ip}")
            except Exception:
                pass

    if not potential_devices:
        print("\n" + "=" * 60)
        print("No devices found with open port 80")
        print("=" * 60)
        print("\nPossible reasons:")
        print("1. The Tapo plug is not connected to WiFi")
        print("2. The plug is on a different network")
        print("3. Firewall is blocking the scan")
        print("\nTry checking the Tapo app to verify the device is online")
        return

    print(f"\n\nStep 2: Testing {len(potential_devices)} device(s) for Tapo...")
    print("=" * 60)

    # Check which ones are Tapo devices
    tapo_devices = []
    for ip in potential_devices:
        print(f"Checking {ip}...", end=" ", flush=True)
        device_info = check_tapo_device(ip, EMAIL, PASSWORD)
        if device_info:
            tapo_devices.append(device_info)
            print("✓ TAPO DEVICE FOUND!")
        else:
            print("not a Tapo device")

    # Display results
    print("\n" + "=" * 60)
    if tapo_devices:
        print(f"SUCCESS! Found {len(tapo_devices)} Tapo device(s)!")
        print("=" * 60)

        for i, device in enumerate(tapo_devices, 1):
            print(f"\n📱 Device {i}:")
            print(f"  IP Address:  {device['ip']}")
            print(f"  Model:       {device['model']}")
            print(f"  Type:        {device['type']}")
            print(f"  Status:      {'ON' if device['device_on'] else 'OFF'}")
            print(f"  MAC Address: {device['mac']}")
            if device['nickname'] != 'Unknown':
                print(f"  Nickname:    {device['nickname']}")

        print("\n" + "=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print(f"Use this IP address: {tapo_devices[0]['ip']}")
        print("\nTo control your plug, run:")
        print(f"  python quick_test.py")
        print("or")
        print(f"  python tapo_control.py")
        print("\nAnd enter the IP address when prompted")
        print("=" * 60)
    else:
        print("No Tapo devices found")
        print("=" * 60)
        print("\nThe devices found don't appear to be Tapo plugs.")
        print("\nTry these steps:")
        print("1. Check the Tapo app to verify the plug is online")
        print("2. Make sure the plug is on the same WiFi network")
        print("3. Try finding the IP in your router's device list")


if __name__ == "__main__":
    main()

