"""
Test different Tuya Cloud API command formats
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from IoS_logins import TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_API_REGION, ARLEC_DEVICE_ID

import tinytuya


def test_all_command_formats():
    """Test every possible command format"""

    print("=" * 70)
    print("Testing ALL Tuya Cloud API Command Formats")
    print("=" * 70)

    # Connect
    cloud = tinytuya.Cloud(
        apiRegion=TUYA_API_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET
    )

    device_id = ARLEC_DEVICE_ID

    # Get current status
    print("\nCurrent device status:")
    status = cloud.getstatus(device_id)
    if status and 'result' in status:
        for item in status['result']:
            print(f"  {item.get('code')}: {item.get('value')}")

    # Try different command formats
    print("\n" + "=" * 70)
    print("Testing Command Formats:")
    print("=" * 70)

    test_commands = [
        # Format 1: Direct key-value
        ("Direct switch_1", {'switch_1': False}),

        # Format 2: Code-value pairs
        ("Code-value", {'code': 'switch_1', 'value': False}),

        # Format 3: Commands array (Tuya Standard)
        ("Commands array", {'commands': [{'code': 'switch_1', 'value': False}]}),

        # Format 4: Just switch
        ("Direct switch", {'switch': False}),

        # Format 5: Commands with code-value
        ("Commands code-value", {'commands': [{'code': 'switch_1', 'value': False}]}),
    ]

    for name, cmd in test_commands:
        print(f"\n[{name}]")
        print(f"  Command: {cmd}")

        result = cloud.sendcommand(device_id, cmd)

        if result.get('success', False):
            print(f"  [OK] SUCCESS!")
            print(f"  Response: {result}")
            break
        else:
            code = result.get('code', 'N/A')
            msg = result.get('msg', 'N/A')
            print(f"  [FAIL] Code: {code}, Msg: {msg}")

    # Try using different TinyTuya methods
    print("\n" + "=" * 70)
    print("Testing Alternative TinyTuya Methods:")
    print("=" * 70)

    # Method 1: Using direct API call
    print("\n[Method 1: Direct API call]")
    try:
        result = cloud.cloudrequest(
            '/v1.0/iot-03/devices/' + device_id + '/commands',
            action='POST',
            post={
                'commands': [
                    {
                        'code': 'switch_1',
                        'value': False
                    }
                ]
            }
        )
        print(f"  Response: {result}")
        if result.get('success', False):
            print("  [OK] SUCCESS!")
    except Exception as e:
        print(f"  Error: {e}")

    # Check device info to see what commands are available
    print("\n" + "=" * 70)
    print("Device Capabilities:")
    print("=" * 70)

    # Get device details
    devices = cloud.getdevices()
    for dev in devices:
        if dev.get('id') == device_id:
            print(f"\nDevice: {dev.get('name')}")
            print(f"Category: {dev.get('category')}")
            print(f"Product ID: {dev.get('product_id')}")

            # Try to get device specification
            try:
                spec_result = cloud.cloudrequest(
                    f'/v1.0/iot-03/devices/{device_id}/specification'
                )
                if 'result' in spec_result:
                    print("\nDevice Functions:")
                    functions = spec_result['result'].get('functions', [])
                    for func in functions:
                        print(f"  - {func.get('code')}: {func.get('type')}")
            except Exception as e:
                print(f"Could not get device spec: {e}")

            break


if __name__ == "__main__":
    test_all_command_formats()
