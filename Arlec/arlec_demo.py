"""
Arlec Smart Plug Demo - Automated demonstration
Shows all features without requiring user input
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from IoS_logins import TUYA_ACCESS_ID, TUYA_ACCESS_SECRET, TUYA_API_REGION, ARLEC_DEVICE_ID

import tinytuya


def demo():
    """Automated demo of Arlec cloud control"""

    print("=" * 70)
    print("Arlec Smart Plug Cloud Control - DEMO")
    print("=" * 70)

    # Connect to cloud
    print("\n[1/6] Connecting to Tuya Cloud API...")
    cloud = tinytuya.Cloud(
        apiRegion=TUYA_API_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET
    )
    print("      [OK] Connected!")

    # Discover devices
    print("\n[2/6] Discovering devices...")
    devices = cloud.getdevices()
    print(f"      [OK] Found {len(devices)} device(s)")

    for dev in devices:
        print(f"\n      Device: {dev.get('name')}")
        print(f"      ID:     {dev.get('id')}")
        print(f"      Model:  {dev.get('model')}")

    device_id = ARLEC_DEVICE_ID

    # Get initial status
    print("\n[3/6] Getting device status...")
    status = cloud.getstatus(device_id)

    if status and 'result' in status:
        print("      [OK] Status retrieved:")
        for item in status['result']:
            code = item.get('code')
            value = item.get('value')
            if code in ['switch_1', 'cur_power', 'cur_voltage', 'cur_current']:
                print(f"      - {code}: {value}")

    # Turn ON
    print("\n[4/6] Turning device ON...")
    result = cloud.sendcommand(
        device_id,
        {'commands': [{'code': 'switch_1', 'value': True}]}
    )

    if result.get('success'):
        print("      [OK] Device is ON")
    else:
        print(f"      [FAIL] {result}")

    time.sleep(2)

    # Check status after turning ON
    print("\n[5/6] Checking status after turning ON...")
    status = cloud.getstatus(device_id)
    if status and 'result' in status:
        for item in status['result']:
            if item.get('code') == 'switch_1':
                state = "ON" if item.get('value') else "OFF"
                print(f"      Current state: {state}")

    time.sleep(2)

    # Turn OFF
    print("\n[6/6] Turning device OFF...")
    result = cloud.sendcommand(
        device_id,
        {'commands': [{'code': 'switch_1', 'value': False}]}
    )

    if result.get('success'):
        print("      [OK] Device is OFF")
    else:
        print(f"      [FAIL] {result}")

    # Final status
    print("\n[FINAL] Final status check...")
    status = cloud.getstatus(device_id)
    if status and 'result' in status:
        for item in status['result']:
            if item.get('code') == 'switch_1':
                state = "ON" if item.get('value') else "OFF"
                print(f"      Current state: {state}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE!")
    print("=" * 70)
    print("\nYour Arlec device is fully functional via Tuya Cloud API!")
    print("\nTo use the interactive controller, run:")
    print("  python arlec_cloud_controller.py")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    demo()
