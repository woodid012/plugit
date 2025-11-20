"""
Device Usage Data Collector
Collects device usage metrics (power, voltage, current, status) and associates with regional price data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import MongoDB credentials
try:
    from IoS_logins import MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_NAME
    DB_NAME = MONGO_DB_NAME
    PRICE_COLLECTION_NAME = MONGO_COLLECTION_NAME
except ImportError:
    MONGO_URI = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
    DB_NAME = "nem_prices"
    PRICE_COLLECTION_NAME = "price_data"

# Device usage collection name
USAGE_COLLECTION_NAME = "device_usage"

# Default region for price lookup
DEFAULT_REGION = "VIC1"

# Timezone
AEST = pytz.timezone('Australia/Sydney')


def connect_mongo() -> Optional[MongoClient]:
    """Connect to MongoDB"""
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"[ERROR] MongoDB connection failed: {e}")
        return None


def round_to_5_minutes(timestamp: datetime) -> datetime:
    """Round timestamp to nearest 5-minute interval"""
    minutes = timestamp.minute
    rounded_minutes = (minutes // 5) * 5
    return timestamp.replace(minute=rounded_minutes, second=0, microsecond=0)


def get_price_at_timestamp(region: str, timestamp: datetime, client: MongoClient, prefer_historical: bool = True) -> Optional[Dict[str, Any]]:
    """
    Get price data from MongoDB for a specific region and timestamp
    
    Args:
        region: NEM region (e.g., 'VIC1')
        timestamp: Datetime to query (should be at end of 5-min interval, e.g., 10:05:00)
        client: MongoDB client
        prefer_historical: If True, prefer historical_price over Forecast_Price
        
    Returns:
        Dict with price data or None if not found
    """
    try:
        db = client[DB_NAME]
        collection = db[PRICE_COLLECTION_NAME]
        
        # The timestamp should already be at the end of the 5-minute interval
        # e.g., 10:05:00 represents the period 10:00:00-10:04:59
        # We want the historical price for that period
        ts_iso = timestamp.isoformat()
        
        # Query for price at this exact timestamp
        query = {
            'region': region,
            'timestamp': ts_iso
        }
        
        doc = collection.find_one(query)
        
        if not doc:
            # Try to find nearest timestamp (within 5 minutes)
            start_ts = (timestamp - timedelta(minutes=5)).isoformat()
            end_ts = (timestamp + timedelta(minutes=5)).isoformat()
            
            query_range = {
                'region': region,
                'timestamp': {
                    '$gte': start_ts,
                    '$lte': end_ts
                }
            }
            
            doc = collection.find_one(query_range, sort=[('timestamp', 1)])
        
        if doc:
            # Extract price - prefer historical_price if prefer_historical=True
            price = None
            price_source = None
            
            if prefer_historical:
                historical_price = doc.get('historical_price')
                if historical_price and isinstance(historical_price, dict):
                    price = historical_price.get('price')
                    price_source = 'historical_price'
                
                # Only use forecast if no historical price available
                if price is None:
                    forecast_price = doc.get('Forecast_Price')
                    if forecast_price is not None:
                        price = forecast_price
                        price_source = 'Forecast_Price'
            else:
                # Use forecast if available, otherwise historical
                forecast_price = doc.get('Forecast_Price')
                if forecast_price is not None:
                    price = forecast_price
                    price_source = 'Forecast_Price'
                else:
                    historical_price = doc.get('historical_price')
                    if historical_price and isinstance(historical_price, dict):
                        price = historical_price.get('price')
                        price_source = 'historical_price'
            
            if price is not None:
                return {
                    'price_per_kwh': price,
                    'price_source': price_source,
                    'timestamp': doc.get('timestamp')
                }
        
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get price at timestamp: {e}")
        return None


def collect_device_usage_data(device_statuses: Dict[str, List[Dict]], use_interval_buffer: bool = True) -> List[Dict[str, Any]]:
    """
    Format device status data for storage
    
    Args:
        device_statuses: Dict with keys 'tapo', 'meross', 'arlec', 'matter' containing device status lists
        use_interval_buffer: If True, add to 30-second buffer and aggregate. If False, use direct collection.
        
    Returns:
        List of formatted device usage records (aggregated if use_interval_buffer=True)
    """
    from .interval_buffer import add_30_second_interval, aggregate_5_minute_intervals
    
    if use_interval_buffer:
        # Add current device data to 30-second interval buffer
        for device_type, devices in device_statuses.items():
            if not devices:
                continue
                
            for device in devices:
                device_id = device.get('id') or device.get('uuid')
                if not device_id:
                    continue
                
                # Add to buffer
                add_30_second_interval(device_id, {
                    'power': device.get('power'),
                    'voltage': device.get('voltage'),
                    'current': device.get('current'),
                    'status': device.get('status', 'unknown'),
                    'online': device.get('online', False)
                })
        
        # Aggregate 5-minute intervals from buffer
        aggregated_records = aggregate_5_minute_intervals()
        
        # Add device metadata to aggregated records
        device_metadata = {}
        for device_type, devices in device_statuses.items():
            for device in devices:
                device_id = device.get('id') or device.get('uuid')
                if device_id:
                    device_metadata[device_id] = {
                        'device_name': device.get('name', 'Unknown Device'),
                        'device_type': device_type
                    }
        
        # Enrich aggregated records with metadata
        for record in aggregated_records:
            device_id = record['device_id']
            if device_id in device_metadata:
                record['device_name'] = device_metadata[device_id]['device_name']
                record['device_type'] = device_metadata[device_id]['device_type']
            else:
                record['device_name'] = 'Unknown Device'
                record['device_type'] = 'unknown'
        
        return aggregated_records
    else:
        # Direct collection (legacy mode)
        usage_records = []
        timestamp = datetime.now(AEST)
        rounded_timestamp = round_to_5_minutes(timestamp)
        
        # Process each device type
        for device_type, devices in device_statuses.items():
            if not devices:
                continue
                
            for device in devices:
                device_id = device.get('id') or device.get('uuid')
                if not device_id:
                    continue
                
                # Extract device data
                record = {
                    'device_id': device_id,
                    'device_name': device.get('name', 'Unknown Device'),
                    'device_type': device_type,
                    'timestamp': rounded_timestamp.isoformat(),
                    'status': device.get('status', 'unknown'),
                    'online': device.get('online', False),
                    'collected_at': timestamp.isoformat()
                }
                
                # Add energy data if available
                if 'power' in device and device['power'] is not None:
                    record['power'] = round(float(device['power']), 2)
                
                if 'voltage' in device and device['voltage'] is not None:
                    record['voltage'] = round(float(device['voltage']), 1)
                
                if 'current' in device and device['current'] is not None:
                    record['current'] = round(float(device['current']), 2)
                
                usage_records.append(record)
        
        return usage_records


def save_device_usage_to_mongodb(
    usage_records: List[Dict[str, Any]],
    region: str = DEFAULT_REGION,
    client: Optional[MongoClient] = None
) -> Dict[str, Any]:
    """
    Save device usage records to MongoDB with associated price data
    
    Args:
        usage_records: List of device usage records
        region: NEM region for price lookup (default: VIC1)
        client: MongoDB client (will create if not provided)
        
    Returns:
        Dict with save statistics
    """
    if not usage_records:
        return {'inserted': 0, 'errors': []}
    
    # Connect to MongoDB if not provided
    if client is None:
        client = connect_mongo()
        if not client:
            return {'inserted': 0, 'errors': ['Failed to connect to MongoDB']}
        close_client = True
    else:
        close_client = False
    
    try:
        db = client[DB_NAME]
        collection = db[USAGE_COLLECTION_NAME]
        
        # Create indexes if they don't exist
        collection.create_index([("device_id", 1), ("timestamp", 1)], unique=True)
        collection.create_index("timestamp")
        collection.create_index("device_id")
        
        inserted = 0
        errors = []
        
        # Process each record
        for record in usage_records:
            try:
                # Get price data for this timestamp (prefer historical/actual price)
                timestamp_dt = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                if timestamp_dt.tzinfo is None:
                    timestamp_dt = AEST.localize(timestamp_dt)
                else:
                    timestamp_dt = timestamp_dt.astimezone(AEST)
                
                # Prefer historical price (actual price for that period)
                price_data = get_price_at_timestamp(region, timestamp_dt, client, prefer_historical=True)
                
                if price_data:
                    record['region'] = region
                    record['price_per_kwh'] = price_data['price_per_kwh']
                    record['price_source'] = price_data['price_source']
                else:
                    record['region'] = region
                    record['price_per_kwh'] = None
                    record['price_source'] = None
                
                # Insert or update (upsert based on device_id + timestamp)
                result = collection.update_one(
                    {
                        'device_id': record['device_id'],
                        'timestamp': record['timestamp']
                    },
                    {'$set': record},
                    upsert=True
                )
                
                if result.upserted_id or result.modified_count > 0:
                    inserted += 1
                    
            except Exception as e:
                error_msg = f"Error saving record for {record.get('device_id', 'unknown')}: {e}"
                errors.append(error_msg)
                print(f"[ERROR] {error_msg}")
        
        return {
            'inserted': inserted,
            'total': len(usage_records),
            'errors': errors
        }
        
    finally:
        if close_client:
            client.close()


def collect_and_save(
    device_statuses: Dict[str, List[Dict]],
    region: str = DEFAULT_REGION
) -> Dict[str, Any]:
    """
    Main function to collect device usage data and save to MongoDB
    
    Args:
        device_statuses: Dict with device status data from server
        region: NEM region for price lookup
        
    Returns:
        Dict with collection and save statistics
    """
    try:
        # Format device data
        usage_records = collect_device_usage_data(device_statuses)
        
        if not usage_records:
            return {
                'success': False,
                'message': 'No device data to collect',
                'records': 0
            }
        
        # Save to MongoDB
        result = save_device_usage_to_mongodb(usage_records, region=region)
        
        return {
            'success': True,
            'records_collected': len(usage_records),
            'records_saved': result['inserted'],
            'errors': result['errors'],
            'region': region
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'records': 0
        }

