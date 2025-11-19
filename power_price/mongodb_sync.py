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
        fetch_p5min_prices,
        fetch_predispatch_prices,
        AEST,
        AEST_FIXED
    )
    from .fetch_dispatch_historical import (
        get_latest_dispatch_file,
        download_and_extract_zip,
        find_csv_file,
        parse_dispatch_csv,
        parse_timestamp_from_filename as parse_dispatch_timestamp
    )
except ImportError:
    # If running as standalone script
    from fetch_prices import (
        fetch_p5min_prices,
        fetch_predispatch_prices,
        AEST,
        AEST_FIXED
    )
    from fetch_dispatch_historical import (
        get_latest_dispatch_file,
        download_and_extract_zip,
        find_csv_file,
        parse_dispatch_csv,
        parse_timestamp_from_filename as parse_dispatch_timestamp
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


def clear_mongodb_collection():
    """
    Clear all documents from the MongoDB price_data collection
    Returns True if successful, False otherwise
    """
    print("=" * 80)
    print("Clearing MongoDB Price Data Collection")
    print("=" * 80)
    
    # Connect to MongoDB
    client = connect_mongodb()
    if not client:
        print("[ERROR] Cannot proceed without MongoDB connection")
        return False
    
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    try:
        # Count documents before deletion
        count_before = collection.count_documents({})
        print(f"[INFO] Found {count_before} documents in collection")
        
        if count_before == 0:
            print("[INFO] Collection is already empty")
            client.close()
            return True
        
        # Delete all documents
        result = collection.delete_many({})
        print(f"[OK] Deleted {result.deleted_count} documents from collection")
        
        # Verify collection is empty
        count_after = collection.count_documents({})
        if count_after == 0:
            print("[OK] Collection successfully cleared")
            client.close()
            return True
        else:
            print(f"[WARNING] Collection still contains {count_after} documents")
            client.close()
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to clear collection: {e}")
        import traceback
        traceback.print_exc()
        client.close()
        return False


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
        
        # 1. Historical dispatch prices (actual settlement data from latest dispatch report)
        print(f"\n[1/3] Fetching historical dispatch prices (latest settlement period)...")
        try:
            # Get latest dispatch file (only fetch once for all regions)
            if region == NEM_REGIONS[0]:  # Only fetch once for first region
                print("[INFO] Getting latest dispatch report...")
                dispatch_result = get_latest_dispatch_file()
                if not dispatch_result:
                    print("[ERROR] Could not find latest dispatch file")
                    errors.append("Could not find latest dispatch file")
                else:
                    dispatch_url, settlement_timestamp = dispatch_result
                    dispatch_filename = os.path.basename(dispatch_url)
                    
                    # Parse expected settlement date from filename
                    expected_settlement_date = parse_dispatch_timestamp(dispatch_filename)
                    if not expected_settlement_date:
                        print(f"[ERROR] Could not parse settlement date from filename: {dispatch_filename}")
                        errors.append(f"Could not parse settlement date from {dispatch_filename}")
                    else:
                        print(f"[INFO] Latest dispatch file: {dispatch_filename}")
                        print(f"[INFO] Settlement period: {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')}")
                        
                        # Download and extract
                        temp_dir = download_and_extract_zip(dispatch_url)
                        if temp_dir:
                            try:
                                # Find CSV file
                                csv_path = find_csv_file(temp_dir.name)
                                if csv_path:
                                    # Parse CSV for all regions at once
                                    print(f"[INFO] Parsing CSV for all regions...")
                                    dispatch_results = parse_dispatch_csv(csv_path, expected_settlement_date, regions=NEM_REGIONS)
                                    
                                    # Store results in a module-level variable for all regions to use
                                    if not hasattr(sync_price_data_to_mongodb, '_dispatch_cache'):
                                        sync_price_data_to_mongodb._dispatch_cache = {}
                                    sync_price_data_to_mongodb._dispatch_cache = {
                                        'source_file': dispatch_filename,
                                        'settlement_timestamp': settlement_timestamp,
                                        'expected_settlement_date': expected_settlement_date,
                                        'results': dispatch_results,
                                        'fetched_at': datetime.now(AEST).isoformat()
                                    }
                                    print(f"[OK] Extracted dispatch data for {len(dispatch_results)} regions")
                                else:
                                    print("[ERROR] No CSV file found in ZIP")
                                    errors.append("No CSV file found in dispatch ZIP")
                            finally:
                                temp_dir.cleanup()
                        else:
                            print("[ERROR] Failed to download/extract dispatch ZIP")
                            errors.append("Failed to download/extract dispatch ZIP")
            
            # Get dispatch data from cache (set by first region)
            dispatch_cache = getattr(sync_price_data_to_mongodb, '_dispatch_cache', None)
            if dispatch_cache and region in dispatch_cache['results']:
                region_data = dispatch_cache['results'][region]
                all_historical_prices = [{
                    'timestamp': region_data['timestamp'],
                    'price': region_data['price']
                }]
                
                dispatch_data = {
                    'region': region,
                    'data_date': region_data['timestamp'],
                    'timezone': datetime.now(AEST).tzname(),
                    'source_file': dispatch_cache['source_file'],
                    'fetched_at': dispatch_cache['fetched_at'],
                    'data_type': 'dispatch_historical',
                    'prices': all_historical_prices
                }
                data_sources['historical'] = dispatch_data
                print(f"[OK] Historical price for {region}: RRP = {region_data['price']:.2f} at {region_data['timestamp']}")
            else:
                print(f"[WARNING] No historical dispatch data for {region}")
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
        # CRITICAL: Only store as historical_price if:
        # 1. Source file is from DISPATCH reports (PUBLIC_DISPATCH_*), NOT predispatch or p5min
        # 2. Timestamp is actually in the past
        now_aest = datetime.now(AEST)
        
        if 'historical' in data_sources:
            source_file = data_sources['historical'].get('source_file', '')
            
            # VALIDATION: Only allow dispatch report files to write to historical_price
            # Reject predispatch and p5min files
            if source_file:
                source_upper = source_file.upper()
                if 'PUBLIC_PREDISPATCH' in source_upper or 'PUBLIC_P5MIN' in source_upper or 'P5MIN' in source_upper or 'PREDISPATCH' in source_upper:
                    print(f"[WARNING] REJECTED: Source file '{source_file}' is from predispatch/p5min, not dispatch. "
                          f"Skipping historical_price update to prevent predispatch data in historical_price field.")
                    # Remove historical from data_sources to prevent it from being processed
                    del data_sources['historical']
                elif 'PUBLIC_DISPATCH' not in source_upper:
                    print(f"[WARNING] REJECTED: Source file '{source_file}' is not a recognized dispatch file. "
                          f"Skipping historical_price update.")
                    del data_sources['historical']
            
            # Only proceed if we still have historical data after validation
            if 'historical' in data_sources:
                # Try both parse functions (dispatch timestamp parser and regular parser)
                source_timestamp = parse_dispatch_timestamp(source_file)
                if source_timestamp:
                    source_timestamp = source_timestamp.strftime('%Y%m%d%H%M')
                else:
                    source_timestamp = parse_timestamp_from_filename(source_file) or data_sources['historical'].get('data_date', '')
                
                # Parse file timestamp for validation
                file_dt = None
                if source_timestamp and len(source_timestamp) >= 12:
                    try:
                        # Parse file timestamp: YYYYMMDDHHMM
                        year = int(source_timestamp[0:4])
                        month = int(source_timestamp[4:6])
                        day = int(source_timestamp[6:8])
                        hour = int(source_timestamp[8:10])
                        minute = int(source_timestamp[10:12])
                        file_dt = AEST_FIXED.localize(datetime(year, month, day, hour, minute))
                    except Exception as e:
                        print(f"[WARNING] Could not parse file timestamp {source_timestamp}: {e}")
                
                for price_point in data_sources['historical'].get('prices', []):
                    ts = price_point['timestamp']
                    
                    # Check if timestamp is actually in the past before storing as historical
                    try:
                        # Parse timestamp
                        if isinstance(ts, str):
                            price_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        else:
                            price_dt = ts
                        
                        # Convert to AEST for comparison
                        if price_dt.tzinfo is None:
                            price_dt = AEST_FIXED.localize(price_dt)
                        elif price_dt.tzinfo != AEST_FIXED:
                            price_dt = price_dt.astimezone(AEST_FIXED)
                        
                        # Validate: settlement timestamp should be at or before file timestamp
                        # Dispatch files are published AFTER settlement, so settlement should be <= file time
                        if file_dt:
                            # Settlement should be at or before file time (allow 5 minute tolerance for edge cases)
                            time_diff = (price_dt - file_dt).total_seconds() / 60  # difference in minutes
                            if time_diff > 5:
                                print(f"[WARNING] Skipping price with timestamp {ts} - settlement time ({price_dt.strftime('%Y-%m-%d %H:%M')}) is {time_diff:.1f} minutes after file time ({file_dt.strftime('%Y-%m-%d %H:%M')}). Dispatch files should contain past settlement data.")
                                continue
                        
                        # Convert now_aest to AEST_FIXED for comparison
                        now_aest_fixed = now_aest.astimezone(AEST_FIXED) if now_aest.tzinfo else AEST_FIXED.localize(now_aest)
                        
                        # Only store as historical if timestamp is in the past
                        is_historical = price_dt < now_aest_fixed
                        
                        if not is_historical:
                            # Skip future timestamps - don't store as historical_price
                            continue
                    except Exception as e:
                        # If we can't parse the timestamp, skip it
                        print(f"[WARNING] Could not parse timestamp {ts} for historical check: {e}")
                        continue
                    
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
                            source_file_value = price_data['source_files'].get(our_type, {}).get('source_file', '')
                            
                            # CRITICAL: For historical_price, validate and clean source_file
                            # Only allow dispatch files, reject predispatch/p5min files
                            if mongo_field == 'historical_price' and source_file_value:
                                # Check if source_file contains any predispatch/p5min files
                                source_upper = source_file_value.upper()
                                if 'PUBLIC_PREDISPATCH' in source_upper or 'PUBLIC_P5MIN' in source_upper or 'P5MIN' in source_upper or 'PREDISPATCH' in source_upper:
                                    # If it's a comma-separated list, filter to only dispatch files
                                    if ',' in source_file_value:
                                        files = [f.strip() for f in source_file_value.split(',')]
                                        dispatch_files = [f for f in files if 'PUBLIC_DISPATCH' in f.upper()]
                                        if dispatch_files:
                                            source_file_value = ', '.join(dispatch_files)
                                        else:
                                            # No dispatch files found - reject this update
                                            print(f"[WARNING] REJECTED: historical_price source_file contains only predispatch/p5min files. Skipping update.")
                                            source_file_value = None
                                    else:
                                        # Single file that's not dispatch - reject
                                        print(f"[WARNING] REJECTED: historical_price source_file is not a dispatch file: {source_file_value}")
                                        source_file_value = None
                                elif 'PUBLIC_DISPATCH' not in source_upper:
                                    # Not a recognized dispatch file - reject
                                    print(f"[WARNING] REJECTED: historical_price source_file is not a recognized dispatch file: {source_file_value}")
                                    source_file_value = None
                            
                            # Only create the update if source_file is valid (or None for non-historical fields)
                            if mongo_field != 'historical_price' or source_file_value is not None:
                                doc_updates[mongo_field] = {
                                    'price': price_data[our_type],
                                    'source_file': source_file_value if source_file_value else '',
                                    'file_timestamp': new_file_ts,
                                    'fetched_at': price_data['source_files'].get(our_type, {}).get('fetched_at', '')
                                }
                            else:
                                # Rejected historical_price update - keep existing or set to None
                                if existing_doc and mongo_field in existing_doc:
                                    # Clean existing data if it has predispatch/p5min files
                                    existing_source = existing_doc[mongo_field].get('source_file', '')
                                    if existing_source and (',' in existing_source or 'PUBLIC_PREDISPATCH' in existing_source.upper() or 'PUBLIC_P5MIN' in existing_source.upper()):
                                        # Clean up existing source_file
                                        if ',' in existing_source:
                                            files = [f.strip() for f in existing_source.split(',')]
                                            dispatch_files = [f for f in files if 'PUBLIC_DISPATCH' in f.upper()]
                                            if dispatch_files:
                                                existing_doc[mongo_field]['source_file'] = ', '.join(dispatch_files)
                                            else:
                                                # No dispatch files - remove historical_price
                                                doc_updates[mongo_field] = None
                                                continue
                                        else:
                                            # Single file that's not dispatch - remove historical_price
                                            doc_updates[mongo_field] = None
                                            continue
                                    doc_updates[mongo_field] = existing_doc[mongo_field]
                                else:
                                    doc_updates[mongo_field] = None
                        elif existing_doc and mongo_field in existing_doc:
                            # Keep existing data if it's newer, but clean it if it's historical_price
                            if mongo_field == 'historical_price':
                                existing_source = existing_doc[mongo_field].get('source_file', '')
                                if existing_source:
                                    # Clean up existing source_file to remove predispatch/p5min files
                                    if ',' in existing_source:
                                        files = [f.strip() for f in existing_source.split(',')]
                                        dispatch_files = [f for f in files if 'PUBLIC_DISPATCH' in f.upper()]
                                        if dispatch_files:
                                            existing_doc[mongo_field]['source_file'] = ', '.join(dispatch_files)
                                        else:
                                            # No dispatch files - remove historical_price
                                            doc_updates[mongo_field] = None
                                            continue
                                    elif 'PUBLIC_PREDISPATCH' in existing_source.upper() or 'PUBLIC_P5MIN' in existing_source.upper():
                                        # Single predispatch/p5min file - remove historical_price
                                        doc_updates[mongo_field] = None
                                        continue
                            doc_updates[mongo_field] = existing_doc[mongo_field]
                    elif existing_doc and mongo_field in existing_doc:
                        # Keep existing data if we don't have new data, but clean it if it's historical_price
                        if mongo_field == 'historical_price':
                            existing_source = existing_doc[mongo_field].get('source_file', '')
                            if existing_source:
                                # Clean up existing source_file to remove predispatch/p5min files
                                if ',' in existing_source:
                                    files = [f.strip() for f in existing_source.split(',')]
                                    dispatch_files = [f for f in files if 'PUBLIC_DISPATCH' in f.upper()]
                                    if dispatch_files:
                                        # Create cleaned copy
                                        cleaned_doc = existing_doc[mongo_field].copy()
                                        cleaned_doc['source_file'] = ', '.join(dispatch_files)
                                        doc_updates[mongo_field] = cleaned_doc
                                    else:
                                        # No dispatch files - remove historical_price
                                        doc_updates[mongo_field] = None
                                elif 'PUBLIC_PREDISPATCH' in existing_source.upper() or 'PUBLIC_P5MIN' in existing_source.upper():
                                    # Single predispatch/p5min file - remove historical_price
                                    doc_updates[mongo_field] = None
                                else:
                                    # Valid dispatch file - keep as is
                                    doc_updates[mongo_field] = existing_doc[mongo_field]
                            else:
                                # No source_file - keep as is
                                doc_updates[mongo_field] = existing_doc[mongo_field]
                        else:
                            # Not historical_price - keep as is
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
    clear_db = '--clear' in sys.argv or '-c' in sys.argv
    
    # Clear database if requested
    if clear_db:
        print("\n[WARNING] Clearing MongoDB collection before re-syncing...")
        if not clear_mongodb_collection():
            print("[ERROR] Failed to clear collection. Aborting.")
            sys.exit(1)
        print("\n" + "=" * 80)
        print("Starting fresh sync after clearing database...")
        print("=" * 80 + "\n")
        # Force refresh when clearing to ensure we get all fresh data
        force_refresh = True
    
    success = sync_price_data_to_mongodb(force_refresh=force_refresh)
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()

