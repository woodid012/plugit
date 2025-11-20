"""
Vercel Serverless Function for Device Usage Collection
This endpoint is triggered by Vercel Cron Jobs every 5 minutes
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from flask import Flask, jsonify, request

# Create a minimal Flask app for Vercel
app = Flask(__name__)

@app.route('/api/cron/collect-device-usage', methods=['GET', 'POST'])
def collect_device_usage():
    """Vercel cron endpoint for device usage collection"""
    try:
        # Import collection function
        from data_collection.device_usage_collector import collect_and_save
        from server import (
            get_tapo_status, get_meross_status_async, get_arlec_status, get_matter_status,
            run_in_meross_loop, get_all_matter_devices,
            KNOWN_DEVICES, tapo_devices_storage, MATTER_AVAILABLE
        )
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        # Get region parameter (default: VIC1)
        region = request.args.get('region', 'VIC1')
        
        # Load Tapo devices
        def load_tapo_devices():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tapo_devices = []
                tapo_tasks = []
                
                for name, ip in KNOWN_DEVICES.items():
                    if 'tapo' in name.lower():
                        tapo_tasks.append((name, ip, None, None, name))
                
                for device_id, device_info in tapo_devices_storage.items():
                    ip = device_info.get('ip')
                    email = device_info.get('email')
                    password = device_info.get('password')
                    device_name = device_info.get('name', device_id)
                    tapo_tasks.append((device_id, ip, email, password, device_name))
                
                async def load_all():
                    tasks = [get_tapo_status(ip, email, password, device_name) 
                            for device_id, ip, email, password, device_name in tapo_tasks]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for i, result in enumerate(results):
                        if not isinstance(result, Exception):
                            device_id = tapo_tasks[i][0]
                            result['id'] = device_id
                            tapo_devices.append(result)
                
                if tapo_tasks:
                    loop.run_until_complete(load_all())
                return tapo_devices
            finally:
                loop.close()
        
        # Load all devices in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            tapo_future = executor.submit(load_tapo_devices)
            meross_future = executor.submit(lambda: run_in_meross_loop(get_meross_status_async()))
            arlec_future = executor.submit(get_arlec_status)
            
            # Matter devices
            def load_matter():
                if not MATTER_AVAILABLE:
                    return []
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    all_matter = get_all_matter_devices()
                    async def load_all():
                        tasks = [get_matter_status(d['device_id'], d.get('ip'), d.get('port', 5540), d.get('name'))
                                for d in all_matter]
                        return await asyncio.gather(*tasks, return_exceptions=True)
                    if all_matter:
                        results = loop.run_until_complete(load_all())
                        return [r for r in results if not isinstance(r, Exception)]
                    return []
                finally:
                    loop.close()
            
            matter_future = executor.submit(load_matter)
            
            tapo_devices = tapo_future.result()
            meross_status = meross_future.result()
            arlec_status = arlec_future.result()
            matter_status = matter_future.result()
        
        # Format device statuses for collection
        device_statuses = {
            'tapo': tapo_devices,
            'meross': meross_status,
            'arlec': arlec_status,
            'matter': matter_status
        }
        
        # Collect and save
        result = collect_and_save(device_statuses, region=region)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Vercel serverless function handler
def handler(request):
    """Vercel serverless function entry point"""
    with app.app_context():
        return collect_device_usage()

