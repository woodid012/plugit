"""
Matter Device Quick Test
Quick connectivity test for Matter devices
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from IoS_logins import MATTER_DEVICES, get_all_matter_devices

try:
    from Matter.matter_controller import MatterController
except ImportError:
    print("[ERROR] Matter controller not found")
    print("Make sure Matter/matter_controller.py exists")
    sys.exit(1)


async def test_matter_device(device_id, ip=None, port=5540, device_name=None):
    """Test a single Matter device"""
    print("\n" + "=" * 60)
    print(f"Testing Matter Device: {device_name or device_id}")
    print("=" * 60)
    
    controller = MatterController(device_id, ip, port)
    
    # Test connection
    print("\n[1/5] Testing connection...")
    if await controller.connect():
        print("[OK] Connected successfully!")
    else:
        print("[FAIL] Connection failed")
        return False
    
    # Test get info
    print("\n[2/5] Getting device information...")
    try:
        info = await controller.get_info()
        if info:
            print("[OK] Device info retrieved")
        else:
            print("[WARN] Device info not available")
    except Exception as e:
        print(f"[WARN] Error getting info: {e}")
    
    # Test get status
    print("\n[3/5] Getting device status...")
    try:
        status = await controller.get_status()
        print(f"[OK] Status: {status.get('status', 'unknown')} ({'Online' if status.get('online') else 'Offline'})")
    except Exception as e:
        print(f"[FAIL] Error getting status: {e}")
        controller.disconnect()
        return False
    
    # Test energy monitoring
    print("\n[4/5] Testing energy monitoring...")
    try:
        energy = await controller.get_energy_usage()
        if energy:
            print("[OK] Energy monitoring available")
            if energy.get('power') is not None:
                print(f"  Power: {energy['power']:.2f} W")
            if energy.get('voltage') is not None:
                print(f"  Voltage: {energy['voltage']:.1f} V")
            if energy.get('current') is not None:
                print(f"  Current: {energy['current']:.2f} A")
        else:
            print("[WARN] Energy monitoring not available")
    except Exception as e:
        print(f"[WARN] Energy monitoring error: {e}")
    
    # Test control (toggle)
    print("\n[5/5] Testing device control...")
    try:
        # Get current state
        status = await controller.get_status()
        current_state = status.get('status') == 'on'
        
        print(f"  Current state: {'ON' if current_state else 'OFF'}")
        print(f"  Toggling device...")
        
        if current_state:
            result = await controller.turn_off()
        else:
            result = await controller.turn_on()
        
        if result:
            print("[OK] Control command sent successfully")
            
            # Wait a moment and check new state
            await asyncio.sleep(1)
            new_status = await controller.get_status()
            new_state = new_status.get('status') == 'on'
            print(f"  New state: {'ON' if new_state else 'OFF'}")
            
            # Toggle back
            print(f"  Restoring original state...")
            if new_state:
                await controller.turn_off()
            else:
                await controller.turn_on()
            print("[OK] Original state restored")
        else:
            print("[FAIL] Control command failed")
    except Exception as e:
        print(f"[FAIL] Control error: {e}")
    
    controller.disconnect()
    print("\n" + "=" * 60)
    print("[SUCCESS] All tests completed!")
    print("=" * 60)
    return True


async def main():
    """Main test function"""
    print("=" * 60)
    print("Matter Device Quick Test")
    print("=" * 60)
    
    # Get all Matter devices
    all_devices = get_all_matter_devices()
    
    if not all_devices:
        print("\n[INFO] No Matter devices configured")
        print("\nTo add a device:")
        print("1. Edit IoS_logins.py")
        print("2. Add device to MATTER_DEVICES dictionary")
        print("3. Format:")
        print("   MATTER_DEVICES = {")
        print("       'device_key': {")
        print("           'device_id': 'your_device_id',")
        print("           'ip': '192.168.x.x',  # Optional")
        print("           'name': 'Device Name',")
        print("           'port': 5540  # Optional")
        print("       }")
        print("   }")
        return
    
    # If only one device, test it automatically
    if len(all_devices) == 1:
        device = all_devices[0]
        await test_matter_device(
            device['device_id'],
            device.get('ip'),
            device.get('port', 5540),
            device.get('name')
        )
    else:
        # Let user choose
        print("\nAvailable Matter Devices:")
        print("-" * 60)
        for i, device in enumerate(all_devices, 1):
            ip_str = f" ({device.get('ip', 'N/A')})" if device.get('ip') else ""
            print(f"{i}. {device.get('name', device['device_id'])}{ip_str}")
        print("-" * 60)
        
        try:
            choice = input(f"\nSelect device to test (1-{len(all_devices)}): ").strip()
            idx = int(choice) - 1
            
            if 0 <= idx < len(all_devices):
                device = all_devices[idx]
                await test_matter_device(
                    device['device_id'],
                    device.get('ip'),
                    device.get('port', 5540),
                    device.get('name')
                )
            else:
                print("Invalid selection")
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled")


if __name__ == "__main__":
    # Windows event loop policy
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")


