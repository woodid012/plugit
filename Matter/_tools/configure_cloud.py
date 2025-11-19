"""
Matter Device Cloud Configuration
Configure Matter devices to upload data directly to cloud services
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import (
    AWS_IOT_ENDPOINT, AWS_IOT_THING_NAME, AWS_IOT_CERT_PATH, AWS_IOT_KEY_PATH, AWS_IOT_ROOT_CA_PATH,
    MQTT_BROKER_URL, MQTT_BROKER_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_TOPIC_PREFIX,
    REST_API_ENDPOINT, REST_API_KEY,
    MATTER_DEVICES, get_all_matter_devices
)


def configure_aws_iot(device_id, device_ip=None):
    """
    Configure Matter device for AWS IoT Core upload
    
    Args:
        device_id: Matter device ID
        device_ip: Device IP address (optional)
    
    Returns:
        Configuration dict for device
    """
    if not AWS_IOT_ENDPOINT:
        print("[ERROR] AWS IoT Core not configured in IoS_logins.py")
        print("Set AWS_IOT_ENDPOINT, AWS_IOT_THING_NAME, and certificate paths")
        return None
    
    config = {
        'cloud_service': 'aws_iot',
        'endpoint': AWS_IOT_ENDPOINT,
        'thing_name': AWS_IOT_THING_NAME or device_id,
        'cert_path': AWS_IOT_CERT_PATH,
        'key_path': AWS_IOT_KEY_PATH,
        'root_ca_path': AWS_IOT_ROOT_CA_PATH,
        'protocol': 'mqtt',
        'port': 8883,  # MQTT over TLS
        'topic': f"matter/devices/{device_id}/data"
    }
    
    print("\n" + "=" * 60)
    print("AWS IoT Core Configuration")
    print("=" * 60)
    print(f"Endpoint: {config['endpoint']}")
    print(f"Thing Name: {config['thing_name']}")
    print(f"Topic: {config['topic']}")
    print(f"Port: {config['port']} (TLS)")
    print("\n[INFO] Device needs to be configured with:")
    print(f"  - Certificate: {config['cert_path']}")
    print(f"  - Private Key: {config['key_path']}")
    print(f"  - Root CA: {config['root_ca_path']}")
    print("\n[NOTE] This configuration should be set on the device itself")
    print("       via device firmware or Matter configuration app")
    
    return config


def configure_mqtt_broker(device_id, device_ip=None):
    """
    Configure Matter device for MQTT broker upload
    
    Args:
        device_id: Matter device ID
        device_ip: Device IP address (optional)
    
    Returns:
        Configuration dict for device
    """
    if not MQTT_BROKER_URL:
        print("[ERROR] MQTT broker not configured in IoS_logins.py")
        print("Set MQTT_BROKER_URL, MQTT_USERNAME, MQTT_PASSWORD")
        return None
    
    config = {
        'cloud_service': 'mqtt',
        'broker_url': MQTT_BROKER_URL,
        'port': MQTT_BROKER_PORT or 8883,
        'username': MQTT_USERNAME,
        'password': MQTT_PASSWORD,
        'topic': f"{MQTT_TOPIC_PREFIX}/{device_id}/data",
        'protocol': 'mqtt',
        'use_tls': True
    }
    
    print("\n" + "=" * 60)
    print("MQTT Broker Configuration")
    print("=" * 60)
    print(f"Broker: {config['broker_url']}:{config['port']}")
    print(f"Topic: {config['topic']}")
    print(f"Username: {config['username']}")
    print(f"TLS: {'Enabled' if config['use_tls'] else 'Disabled'}")
    print("\n[INFO] Device needs to be configured with:")
    print(f"  - Broker URL: {config['broker_url']}")
    print(f"  - Port: {config['port']}")
    print(f"  - Username: {config['username']}")
    print(f"  - Password: {config['password']}")
    print(f"  - Topic: {config['topic']}")
    print("\n[NOTE] This configuration should be set on the device itself")
    print("       via device firmware or Matter configuration app")
    
    return config


def configure_rest_api(device_id, device_ip=None):
    """
    Configure Matter device for REST API upload
    
    Args:
        device_id: Matter device ID
        device_ip: Device IP address (optional)
    
    Returns:
        Configuration dict for device
    """
    if not REST_API_ENDPOINT:
        print("[ERROR] REST API endpoint not configured in IoS_logins.py")
        print("Set REST_API_ENDPOINT and REST_API_KEY")
        return None
    
    config = {
        'cloud_service': 'rest',
        'endpoint': REST_API_ENDPOINT,
        'api_key': REST_API_KEY,
        'protocol': 'https',
        'method': 'POST',
        'headers': {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {REST_API_KEY}'
        }
    }
    
    print("\n" + "=" * 60)
    print("REST API Configuration")
    print("=" * 60)
    print(f"Endpoint: {config['endpoint']}")
    print(f"Method: {config['method']}")
    print(f"API Key: {'*' * 20} (configured)")
    print("\n[INFO] Device needs to be configured with:")
    print(f"  - Endpoint URL: {config['endpoint']}")
    print(f"  - API Key: {config['api_key']}")
    print(f"  - Data format: JSON POST with device_id, timestamp, power, voltage, current")
    print("\n[NOTE] This configuration should be set on the device itself")
    print("       via device firmware or Matter configuration app")
    
    return config


def generate_device_config(device_id, cloud_service='aws_iot'):
    """
    Generate configuration for a Matter device
    
    Args:
        device_id: Matter device ID
        cloud_service: 'aws_iot', 'mqtt', or 'rest'
    
    Returns:
        Configuration dict
    """
    device_info = None
    for dev_id, dev_info in MATTER_DEVICES.items():
        if dev_info.get('device_id') == device_id or dev_id == device_id:
            device_info = dev_info
            break
    
    if not device_info:
        print(f"[ERROR] Device {device_id} not found in MATTER_DEVICES")
        return None
    
    device_ip = device_info.get('ip')
    
    if cloud_service == 'aws_iot':
        return configure_aws_iot(device_id, device_ip)
    elif cloud_service == 'mqtt':
        return configure_mqtt_broker(device_id, device_ip)
    elif cloud_service == 'rest':
        return configure_rest_api(device_id, device_ip)
    else:
        print(f"[ERROR] Unknown cloud service: {cloud_service}")
        print("Available: 'aws_iot', 'mqtt', 'rest'")
        return None


def save_config_to_file(device_id, config, filename=None):
    """
    Save device configuration to JSON file
    
    Args:
        device_id: Matter device ID
        config: Configuration dict
        filename: Output filename (optional)
    """
    if not filename:
        filename = f"matter_device_{device_id}_cloud_config.json"
    
    output_path = Path(__file__).parent / filename
    
    config_data = {
        'device_id': device_id,
        'timestamp': json.dumps({}, default=str),  # Will be replaced with actual timestamp
        'configuration': config
    }
    
    # Add actual timestamp
    from datetime import datetime
    config_data['timestamp'] = datetime.now().isoformat()
    
    with open(output_path, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    print(f"\n[OK] Configuration saved to: {output_path}")
    return output_path


def main():
    """Main configuration menu"""
    print("=" * 60)
    print("Matter Device Cloud Configuration")
    print("=" * 60)
    
    # Get all Matter devices
    all_devices = get_all_matter_devices()
    
    if not all_devices:
        print("\n[INFO] No Matter devices configured")
        print("Add devices to MATTER_DEVICES in IoS_logins.py first")
        return
    
    # Select device
    print("\nAvailable Matter Devices:")
    print("-" * 60)
    for i, device in enumerate(all_devices, 1):
        print(f"{i}. {device.get('name', device['device_id'])} ({device['device_id']})")
    print("-" * 60)
    
    try:
        choice = input(f"\nSelect device (1-{len(all_devices)}): ").strip()
        idx = int(choice) - 1
        
        if not (0 <= idx < len(all_devices)):
            print("Invalid selection")
            return
        
        device = all_devices[idx]
        device_id = device['device_id']
        
        # Select cloud service
        print("\n" + "=" * 60)
        print("Select Cloud Service:")
        print("=" * 60)
        print("1. AWS IoT Core (Recommended)")
        print("2. MQTT Broker")
        print("3. REST API")
        print("-" * 60)
        
        service_choice = input("\nSelect service (1-3): ").strip()
        
        cloud_service = None
        if service_choice == '1':
            cloud_service = 'aws_iot'
        elif service_choice == '2':
            cloud_service = 'mqtt'
        elif service_choice == '3':
            cloud_service = 'rest'
        else:
            print("Invalid selection")
            return
        
        # Generate configuration
        config = generate_device_config(device_id, cloud_service)
        
        if config:
            # Ask to save to file
            save = input("\nSave configuration to file? (y/n): ").strip().lower()
            if save == 'y':
                save_config_to_file(device_id, config)
            
            print("\n[SUCCESS] Configuration generated!")
            print("\n[IMPORTANT] Next steps:")
            print("1. Configure your Matter device with the settings above")
            print("2. Device firmware/app should support cloud upload configuration")
            print("3. Test connectivity from device to cloud service")
            print("4. Monitor cloud service to verify data upload")
    
    except (ValueError, IndexError) as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\n\nCancelled by user")


if __name__ == "__main__":
    main()


