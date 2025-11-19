"""
MongoDB Sync for NEMweb Power Price Data
Syncs historical, dispatch 5-minute, and dispatch 30-minute (predispatch) data to MongoDB
for all NEM regions (VIC1, NSW1, QLD1, SA1, TAS1)

Priority for Export_Price: historical > dispatch_5min > dispatch_30min (predispatch)
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure
import pytz

try:
    from .fetch_prices import (
        fetch_dispatch_prices,
        fetch_p5min_prices,
        fetch_predispatch_prices,
        AEST
    )
except ImportError:
    # If running as standalone script
    from fetch_prices import (
        fetch_dispatch_prices,
        fetch_p5min_prices,
        fetch_predispatch_prices,
        AEST
    )

# MongoDB connection details
MONGO_USERNAME = "NEMprice"
MONGO_PASSWORD = "test_smart123"
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"

# NEM regions (states)
NEM_REGIONS = ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']

# Database and collection names
DB_NAME = "nem_prices"
COLLECTION_NAME = "price_data"


def connect_mongodb() -> Optional[MongoClient]:
    """
    Connect to MongoDB and return client
    """
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        # Test connection
        client.admin.command('ping')
        print("[OK] Successfully connected to MongoDB!")
        return client
    except ConnectionFailure as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] MongoDB connection error: {e}")
        return None


def parse_timestamp_from_filename(filename: str) -> Optional[str]:
    """
    Extract timestamp from NEMweb filename
    Examples:
    - PUBLIC_DISPATCH_202511182020_20251118201515_LEGACY.zip -> 202511182020
    - PUBLIC_P5MIN_202511182020_20251118201530.zip -> 202511182020
    - PUBLIC_PREDISPATCH_202511182030_20251118202530.zip -> 202511182030
    """
    import re
    # Pattern matches YYYYMMDDHHMM (12 digits)
    match = re.search(r'(\d{12})', filename)
    if match:
        return match.group(1)
    return None


def compare_timestamps(ts1: str, ts2: str) -> int:
    """
    Compare two timestamp strings (YYYYMMDDHHMM format)
    Returns: -1 if ts1 < ts2, 0 if equal, 1 if ts1 > ts2
    """
    if ts1 < ts2:
        return -1
    elif ts1 > ts2:
        return 1
    return 0


def get_existing_document_timestamp(db, region: str, price_timestamp: str) -> Optional[str]:
    """
    Get the source_file timestamp for an existing document
    Returns the timestamp string from the source_file, or None if document doesn't exist
    """
    collection = db[COLLECTION_NAME]
    doc = collection.find_one({
        'region': region,
        'timestamp': price_timestamp
    })
    
    if doc:
        # Get the latest source_file timestamp from all data types
        timestamps = []
        for data_type in ['historical_price', 'dispatch_5min', 'dispatch_30min']:
            if data_type in doc and doc[data_type] and 'source_file' in doc[data_type]:
                ts = parse_timestamp_from_filename(doc[data_type]['source_file'])
                if ts:
                    timestamps.append(ts)
        
        if timestamps:
            return max(timestamps)
    
    return None


def calculate_export_price(historical: Optional[float], p5min: Optional[float], 
                           predispatch: Optional[float]) -> Optional[float]:
    """
    Calculate Export_Price using priority:
    1. historical_price (dispatch)
    2. dispatch_5min (p5min)
    3. dispatch_30min (predispatch)
    """
    if historical is not None:
        return historical
    elif p5min is not None:
        return p5min
    elif predispatch is not None:
        return predispatch
    return None


def calculate_forecast_price(p5min: Optional[float], predispatch: Optional[float]) -> Optional[float]:
    """
    Calculate Forecast_Price using priority:
    1. dispatch_5min (p5min) - 5-minute predispatch
    2. dispatch_30min (predispatch) - 30-minute predispatch
    """
    if p5min is not None:
        return p5min
    elif predispatch is not None:
        return predispatch
    return None


def sync_price_data_to_mongodb(force_refresh: bool = False):
    """
    Main function to sync all price data to MongoDB
    Fetches data for all regions and all data types
    """
    print("=" * 80)
    print("MongoDB NEMweb Price Data Sync")
    print("=" * 80)
    
    # Connect to MongoDB
    client = connect_mongodb()
    if not client:
        print("[ERROR] Cannot proceed without MongoDB connection")
        return False
    
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    # Create indexes for efficient queries
    try:
        collection.create_index([("region", 1), ("timestamp", 1)], unique=True)
        collection.create_index([("timestamp", 1)])
        collection.create_index([("region", 1)])
        print("[OK] Database indexes created/verified")
    except Exception as e:
        print(f"[WARNING] Index creation: {e}")
    
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    errors = []
    
    # Fetch data for each region
    for region in NEM_REGIONS:
        print(f"\n{'='*80}")
        print(f"Processing region: {region}")
        print(f"{'='*80}")
        
        # Fetch all three data types
        data_sources = {}
        
        # 1. Historical dispatch prices (last 1 hour of actual prices)
        # We need to fetch multiple dispatch files to get a full hour (12 x 5-minute intervals)
        print(f"\n[1/3] Fetching historical dispatch prices for {region} (last 1 hour)...")
        try:
            all_historical_prices = []
            all_source_files = []
            
            # Fetch the latest dispatch file first
            latest_dispatch = fetch_dispatch_prices(region=region, hours_back=1, force_refresh=force_refresh)
            if latest_dispatch and latest_dispatch.get('prices'):
                all_historical_prices.extend(latest_dispatch['prices'])
                all_source_files.append(latest_dispatch.get('source_file', ''))
            
            # Now collect prices from cache AND MongoDB to build up the last hour
            # Each dispatch file contains one 5-minute interval, so we need ~12 files for 1 hour
            from datetime import timedelta
            from fetch_prices import load_unified_cache, AEST_FIXED
            
            # Get current time in AEST
            now_aest = datetime.now(AEST)
            # Calculate cutoff time (1 hour ago)
            cutoff_time = now_aest - timedelta(hours=1)
            # Also allow up to 15 minutes in future (dispatch can be slightly ahead)
            future_limit = now_aest + timedelta(minutes=15)
            
            # Convert to ISO strings for MongoDB query
            cutoff_iso = cutoff_time.astimezone(AEST_FIXED).isoformat() if cutoff_time.tzinfo else AEST_FIXED.localize(cutoff_time).isoformat()
            future_iso = future_limit.astimezone(AEST_FIXED).isoformat() if future_limit.tzinfo else AEST_FIXED.localize(future_limit).isoformat()
            
            # Query MongoDB for existing historical data in the last hour
            # Use Export_Price as it has the best available price (historical > p5min > predispatch)
            try:
                existing_docs = collection.find({
                    'region': region,
                    'timestamp': {
                        '$gte': cutoff_iso,
                        '$lte': future_iso
                    },
                    'Export_Price': {'$ne': None}
                }).sort('timestamp', 1)
                
                for doc in existing_docs:
                    # Prefer historical_price if available, otherwise use Export_Price
                    hist_price = doc.get('historical_price', {})
                    export_price = doc.get('Export_Price')
                    
                    # Use historical_price if available, otherwise Export_Price
                    price_value = None
                    source_file = None
                    
                    if hist_price and isinstance(hist_price, dict) and hist_price.get('price') is not None:
                        price_value = hist_price['price']
                        source_file = hist_price.get('source_file')
                    elif export_price is not None:
                        # Use Export_Price as fallback (it's calculated from best available source)
                        price_value = export_price
                        # Try to get source file from any available price source
                        dispatch_5min = doc.get('dispatch_5min')
                        dispatch_30min = doc.get('dispatch_30min')
                        if dispatch_5min and isinstance(dispatch_5min, dict) and dispatch_5min.get('source_file'):
                            source_file = dispatch_5min['source_file']
                        elif dispatch_30min and isinstance(dispatch_30min, dict) and dispatch_30min.get('source_file'):
                            source_file = dispatch_30min['source_file']
                    
                    if price_value is not None:
                        price_entry = {
                            'timestamp': doc['timestamp'],
                            'price': price_value
                        }
                        # Check if we already have this timestamp
                        if not any(p['timestamp'] == price_entry['timestamp'] for p in all_historical_prices):
                            all_historical_prices.append(price_entry)
                            if source_file:
                                all_source_files.append(source_file)
            except Exception as e:
                print(f"[WARNING] Could not query MongoDB for historical data: {e}")
            
            # Also collect from cache (in case we have newer data not yet in MongoDB)
            cache = load_unified_cache()
            if 'dispatch' in cache and cache['dispatch']:
                for timestamp_key, dispatch_entry in cache['dispatch'].items():
                    if dispatch_entry and dispatch_entry.get('region') == region:
                        entry_prices = dispatch_entry.get('prices', [])
                        for price in entry_prices:
                            try:
                                price_ts_str = price['timestamp']
                                # Parse timestamp (handle both with and without timezone)
                                if 'T' in price_ts_str:
                                    price_dt = datetime.fromisoformat(price_ts_str.replace('Z', '+00:00'))
                                else:
                                    continue
                                
                                # Ensure timezone-aware
                                if price_dt.tzinfo is None:
                                    price_dt = AEST_FIXED.localize(price_dt.replace(tzinfo=None))
                                
                                # Convert to AEST for comparison
                                if price_dt.tzinfo != AEST_FIXED:
                                    price_dt = price_dt.astimezone(AEST_FIXED)
                                
                                # Convert cutoff and future_limit to AEST_FIXED for comparison
                                cutoff_aest = cutoff_time.astimezone(AEST_FIXED) if cutoff_time.tzinfo else AEST_FIXED.localize(cutoff_time)
                                future_aest = future_limit.astimezone(AEST_FIXED) if future_limit.tzinfo else AEST_FIXED.localize(future_limit)
                                
                                # Check if within our time window
                                if cutoff_aest <= price_dt <= future_aest:
                                    # Check if we already have this timestamp
                                    if not any(p['timestamp'] == price['timestamp'] for p in all_historical_prices):
                                        all_historical_prices.append(price)
                                        if dispatch_entry.get('source_file'):
                                            all_source_files.append(dispatch_entry['source_file'])
                            except Exception as e:
                                # Skip problematic entries
                                continue
            
            # Sort by timestamp
            all_historical_prices.sort(key=lambda x: x['timestamp'])
            
            if all_historical_prices:
                # Create combined dispatch data structure
                dispatch_data = {
                    'region': region,
                    'data_date': latest_dispatch.get('data_date', '') if latest_dispatch else '',
                    'timezone': latest_dispatch.get('timezone', 'AEST') if latest_dispatch else 'AEST',
                    'source_file': ', '.join(sorted(set(all_source_files))) if all_source_files else '',
                    'fetched_at': datetime.now(AEST).isoformat(),
                    'hours_back': 1,
                    'data_type': 'dispatch_historical',
                    'prices': all_historical_prices
                }
                data_sources['historical'] = dispatch_data
                print(f"[OK] Fetched {len(all_historical_prices)} historical price points (target: 12 for 1 hour)")
            else:
                print(f"[WARNING] No historical data for {region}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch historical data for {region}: {e}")
            import traceback
            traceback.print_exc()
            errors.append(f"{region} historical: {e}")
        
        # 2. 5-minute predispatch
        print(f"\n[2/3] Fetching 5-minute predispatch for {region}...")
        try:
            p5min_data = fetch_p5min_prices(region=region, hours_ahead=0, force_refresh=force_refresh)
            if p5min_data:
                data_sources['p5min'] = p5min_data
                print(f"[OK] Fetched {len(p5min_data['prices'])} 5-minute price points")
            else:
                print(f"[WARNING] No 5-minute data for {region}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch 5-minute data for {region}: {e}")
            errors.append(f"{region} p5min: {e}")
        
        # 3. 30-minute predispatch (full predispatch)
        print(f"\n[3/3] Fetching 30-minute predispatch for {region}...")
        try:
            predispatch_data = fetch_predispatch_prices(region=region, hours_ahead=24, force_refresh=force_refresh)
            if predispatch_data:
                data_sources['predispatch'] = predispatch_data
                print(f"[OK] Fetched {len(predispatch_data['prices'])} 30-minute price points")
            else:
                print(f"[WARNING] No 30-minute data for {region}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch 30-minute data for {region}: {e}")
            errors.append(f"{region} predispatch: {e}")
        
        # Organize price data by timestamp
        price_map = {}  # timestamp -> {historical, p5min, predispatch, source_files}
        
        # Process historical data
        if 'historical' in data_sources:
            source_file = data_sources['historical'].get('source_file', '')
            source_timestamp = parse_timestamp_from_filename(source_file) or data_sources['historical'].get('data_date', '')
            
            for price_point in data_sources['historical'].get('prices', []):
                ts = price_point['timestamp']
                if ts not in price_map:
                    price_map[ts] = {
                        'historical': None,
                        'p5min': None,
                        'predispatch': None,
                        'source_files': {}
                    }
                price_map[ts]['historical'] = price_point['price']
                price_map[ts]['source_files']['historical'] = {
                    'source_file': source_file,
                    'file_timestamp': source_timestamp,
                    'fetched_at': data_sources['historical'].get('fetched_at', '')
                }
        
        # Process 5-minute data
        if 'p5min' in data_sources:
            source_file = data_sources['p5min'].get('source_file', '')
            source_timestamp = parse_timestamp_from_filename(source_file) or data_sources['p5min'].get('data_date', '')
            
            for price_point in data_sources['p5min'].get('prices', []):
                ts = price_point['timestamp']
                if ts not in price_map:
                    price_map[ts] = {
                        'historical': None,
                        'p5min': None,
                        'predispatch': None,
                        'source_files': {}
                    }
                price_map[ts]['p5min'] = price_point['price']
                price_map[ts]['source_files']['p5min'] = {
                    'source_file': source_file,
                    'file_timestamp': source_timestamp,
                    'fetched_at': data_sources['p5min'].get('fetched_at', '')
                }
        
        # Process predispatch data
        if 'predispatch' in data_sources:
            source_file = data_sources['predispatch'].get('source_file', '')
            source_timestamp = parse_timestamp_from_filename(source_file) or data_sources['predispatch'].get('data_date', '')
            
            for price_point in data_sources['predispatch'].get('prices', []):
                ts = price_point['timestamp']
                if ts not in price_map:
                    price_map[ts] = {
                        'historical': None,
                        'p5min': None,
                        'predispatch': None,
                        'source_files': {}
                    }
                price_map[ts]['predispatch'] = price_point['price']
                price_map[ts]['source_files']['predispatch'] = {
                    'source_file': source_file,
                    'file_timestamp': source_timestamp,
                    'fetched_at': data_sources['predispatch'].get('fetched_at', '')
                }
        
        # Insert/update documents in MongoDB
        print(f"\n[SYNC] Syncing {len(price_map)} price points to MongoDB...")
        
        for price_timestamp, price_data in price_map.items():
            try:
                # Calculate Export_Price
                export_price = calculate_export_price(
                    price_data['historical'],
                    price_data['p5min'],
                    price_data['predispatch']
                )
                
                # Get existing document to check if we should update
                existing_doc = collection.find_one({
                    'region': region,
                    'timestamp': price_timestamp
                })
                
                # Prepare document with smart update logic per data type
                # Only update a data type if the new file timestamp is >= existing
                doc_updates = {
                    'region': region,
                    'timestamp': price_timestamp,
                    'last_updated': datetime.now(AEST).isoformat()
                }
                
                # Map our data types to MongoDB field names
                data_type_map = {
                    'historical': 'historical_price',
                    'p5min': 'dispatch_5min',
                    'predispatch': 'dispatch_30min'
                }
                
                # Check each data type individually
                for our_type, mongo_field in data_type_map.items():
                    if price_data[our_type] is not None:
                        new_file_ts = price_data['source_files'].get(our_type, {}).get('file_timestamp', '')
                        
                        # Check if we should update this data type
                        should_update_type = True
                        if existing_doc and mongo_field in existing_doc and existing_doc[mongo_field]:
                            existing_file_ts = parse_timestamp_from_filename(
                                existing_doc[mongo_field].get('source_file', '')
                            ) or existing_doc[mongo_field].get('file_timestamp', '')
                            
                            if existing_file_ts and new_file_ts:
                                # Only update if new timestamp >= existing (overwrite if same or newer)
                                if new_file_ts < existing_file_ts:
                                    should_update_type = False
                        
                        if should_update_type:
                            doc_updates[mongo_field] = {
                                'price': price_data[our_type],
                                'source_file': price_data['source_files'].get(our_type, {}).get('source_file', ''),
                                'file_timestamp': new_file_ts,
                                'fetched_at': price_data['source_files'].get(our_type, {}).get('fetched_at', '')
                            }
                        elif existing_doc and mongo_field in existing_doc:
                            # Keep existing data if it's newer
                            doc_updates[mongo_field] = existing_doc[mongo_field]
                    elif existing_doc and mongo_field in existing_doc:
                        # Keep existing data if we don't have new data
                        doc_updates[mongo_field] = existing_doc[mongo_field]
                    else:
                        # No data available
                        doc_updates[mongo_field] = None
                
                # Recalculate Export_Price based on final document state
                final_export_price = calculate_export_price(
                    doc_updates.get('historical_price', {}).get('price') if doc_updates.get('historical_price') else None,
                    doc_updates.get('dispatch_5min', {}).get('price') if doc_updates.get('dispatch_5min') else None,
                    doc_updates.get('dispatch_30min', {}).get('price') if doc_updates.get('dispatch_30min') else None
                )
                doc_updates['Export_Price'] = final_export_price
                
                # Calculate Forecast_Price (5-minute if available, otherwise 30-minute)
                final_forecast_price = calculate_forecast_price(
                    doc_updates.get('dispatch_5min', {}).get('price') if doc_updates.get('dispatch_5min') else None,
                    doc_updates.get('dispatch_30min', {}).get('price') if doc_updates.get('dispatch_30min') else None
                )
                doc_updates['Forecast_Price'] = final_forecast_price
                
                # Check if we're actually updating anything new
                if existing_doc:
                    # Always update if Forecast_Price is missing (backfill for older documents)
                    needs_forecast_backfill = 'Forecast_Price' not in existing_doc or existing_doc.get('Forecast_Price') is None
                    
                    # Compare to see if anything changed
                    has_changes = needs_forecast_backfill
                    if not has_changes:
                        for field in ['historical_price', 'dispatch_5min', 'dispatch_30min', 'Export_Price', 'Forecast_Price']:
                            if field not in existing_doc or existing_doc.get(field) != doc_updates.get(field):
                                has_changes = True
                                break
                    
                    if not has_changes:
                        total_skipped += 1
                        continue
                
                # Update or insert
                result = collection.update_one(
                    {'region': region, 'timestamp': price_timestamp},
                    {'$set': doc_updates},
                    upsert=True
                )
                
                if result.upserted_id:
                    total_inserted += 1
                else:
                    total_updated += 1
                    
            except Exception as e:
                print(f"[ERROR] Failed to sync price point {price_timestamp} for {region}: {e}")
                errors.append(f"{region} {price_timestamp}: {e}")
        
        print(f"[OK] Region {region}: {len(price_map)} price points processed")
    
    # Summary
    print("\n" + "=" * 80)
    print("SYNC SUMMARY")
    print("=" * 80)
    print(f"Total inserted: {total_inserted}")
    print(f"Total updated: {total_updated}")
    print(f"Total skipped (older data): {total_skipped}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nErrors encountered:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    client.close()
    print("\n[OK] MongoDB sync completed!")
    return len(errors) == 0


def main():
    """
    Main entry point
    """
    import sys
    
    force_refresh = '--refresh' in sys.argv or '-r' in sys.argv
    
    success = sync_price_data_to_mongodb(force_refresh=force_refresh)
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()

