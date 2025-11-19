"""
MongoDB Sync for NEMweb Power Prices
Syncs historical, 5-minute, and 30-minute dispatch data to MongoDB for all NEM regions
"""

import sys
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# Local imports
try:
    from .fetch_prices import fetch_p5min_prices, fetch_predispatch_prices, AEST
    from .fetch_dispatch_historical import fetch_historical_dispatch_all_regions
except ImportError:
    from fetch_prices import fetch_p5min_prices, fetch_predispatch_prices, AEST
    from fetch_dispatch_historical import fetch_historical_dispatch_all_regions

# Import MongoDB credentials from centralized config
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from IoS_logins import MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_NAME
    DB_NAME = MONGO_DB_NAME
    COLLECTION_NAME = MONGO_COLLECTION_NAME
except ImportError:
    # Fallback if IoS_logins.py not available
    MONGO_URI = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
    DB_NAME = "nem_prices"
    COLLECTION_NAME = "price_data"

# Config
REGIONS = ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']


# Helpers
def connect_mongo() -> Optional[MongoClient]:
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("[OK] Connected to MongoDB")
        return client
    except Exception as e:
        print(f"[ERROR] MongoDB connection failed: {e}")
        return None


def is_dispatch_file(filename: str) -> bool:
    """Check if filename is a dispatch file (not predispatch or p5min)"""
    filename_upper = filename.upper()
    # Dispatch files contain PUBLIC_DISPATCH but not PREDISPATCH or P5MIN
    return 'PUBLIC_DISPATCH' in filename_upper and 'PREDISPATCH' not in filename_upper and 'P5MIN' not in filename_upper


def parse_file_timestamp(filename: str) -> Optional[str]:
    match = re.search(r'(\d{12})', filename)
    return match.group(1) if match else None


def create_price_record(price: float, source_file: str, fetched_at: str) -> Dict:
    return {
        'price': price,
        'source_file': source_file,
        'file_timestamp': parse_file_timestamp(source_file),
        'fetched_at': fetched_at
    }


def get_forecast_price(doc: Dict) -> Optional[float]:
    dispatch_5min = doc.get('dispatch_5min')
    if dispatch_5min and isinstance(dispatch_5min, dict):
        return dispatch_5min.get('price')
    dispatch_30min = doc.get('dispatch_30min')
    if dispatch_30min and isinstance(dispatch_30min, dict):
        return dispatch_30min.get('price')
    return None


def cleanup_old_forecasts(client: MongoClient, max_age_hours: int = 2) -> Dict[str, int]:
    """
    Remove forecast data (dispatch_5min and dispatch_30min) older than max_age_hours.
    Preserves historical_price data indefinitely.
    
    Args:
        client: MongoDB client
        max_age_hours: Maximum age in hours for forecast data (default: 2)
    
    Returns:
        Dictionary with cleanup statistics: {'removed_5min': int, 'removed_30min': int, 'documents_updated': int}
    """
    db = client[DB_NAME]
    coll = db[COLLECTION_NAME]
    
    cutoff_time = datetime.now(AEST) - timedelta(hours=max_age_hours)
    cutoff_iso = cutoff_time.isoformat()
    
    stats = {
        'removed_5min': 0,
        'removed_30min': 0,
        'documents_updated': 0
    }
    
    print(f"\n[CLEANUP] Removing forecast data older than {max_age_hours} hours (before {cutoff_iso})...")
    
    # Find all documents that might have old forecast data
    # We need to check each document's timestamp against the cutoff
    query = {
        '$or': [
            {'dispatch_5min': {'$exists': True}},
            {'dispatch_30min': {'$exists': True}}
        ]
    }
    
    documents = coll.find(query)
    updated_count = 0
    
    for doc in documents:
        timestamp_str = doc.get('timestamp')
        if not timestamp_str:
            continue
        
        # Parse timestamp if it's a string
        if isinstance(timestamp_str, str):
            try:
                # Handle ISO format timestamps
                if '+' in timestamp_str or timestamp_str.endswith('Z'):
                    # Parse ISO format
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    doc_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    # Convert to AEST if needed
                    if doc_time.tzinfo is None:
                        doc_time = AEST.localize(doc_time)
                    else:
                        doc_time = doc_time.astimezone(AEST)
                else:
                    # Try parsing as ISO without timezone
                    doc_time = datetime.fromisoformat(timestamp_str)
                    if doc_time.tzinfo is None:
                        doc_time = AEST.localize(doc_time)
            except (ValueError, AttributeError):
                continue
        else:
            # Already a datetime object
            doc_time = timestamp_str
            if doc_time.tzinfo is None:
                doc_time = AEST.localize(doc_time)
            else:
                doc_time = doc_time.astimezone(AEST)
        
        # Check if this document's timestamp is older than cutoff
        if doc_time < cutoff_time:
            update_fields = {}
            
            # Remove dispatch_5min if it exists
            if 'dispatch_5min' in doc:
                update_fields['$unset'] = {'dispatch_5min': ''}
                stats['removed_5min'] += 1
            
            # Remove dispatch_30min if it exists
            if 'dispatch_30min' in doc:
                if '$unset' not in update_fields:
                    update_fields['$unset'] = {}
                update_fields['$unset']['dispatch_30min'] = ''
                stats['removed_30min'] += 1
            
            # Also remove Forecast_Price if it was based on forecast data
            if 'Forecast_Price' in doc:
                if '$unset' not in update_fields:
                    update_fields['$unset'] = {}
                update_fields['$unset']['Forecast_Price'] = ''
            
            if update_fields:
                if '$set' not in update_fields:
                    update_fields['$set'] = {}
                update_fields['$set']['last_updated'] = datetime.now(AEST).isoformat()
                
                # Perform update
                result = coll.update_one(
                    {'_id': doc['_id']},
                    update_fields
                )
                
                if result.modified_count > 0:
                    updated_count += 1
    
    stats['documents_updated'] = updated_count
    print(f"[CLEANUP] Removed {stats['removed_5min']} dispatch_5min entries")
    print(f"[CLEANUP] Removed {stats['removed_30min']} dispatch_30min entries")
    print(f"[CLEANUP] Updated {updated_count} documents")
    
    return stats


# Historical-only sync function (for hourly automation)
def sync_historical_only(hours_back: int = 1, force_refresh: bool = False) -> bool:
    """
    Sync only historical dispatch prices, ignoring forecast data.
    Used for hourly automation to ensure historical data collection is complete.
    
    Args:
        hours_back: Number of hours of historical data to fetch (default: 1 hour = 12 data points)
        force_refresh: Force re-fetch even if cached data exists
    
    Returns:
        True if successful, False otherwise
    """
    client = connect_mongo()
    if not client:
        return False

    db = client[DB_NAME]
    coll = db[COLLECTION_NAME]

    # Indexes
    coll.create_index([("region", 1), ("timestamp", 1)], unique=True)
    coll.create_index("timestamp")
    coll.create_index("region")

    total_inserted = total_updated = total_skipped = 0
    errors: List[str] = []

    print("\n" + "="*80)
    print(f"HISTORICAL DISPATCH SYNC - LAST {hours_back} HOUR(S) - ALL REGIONS")
    print("="*80 + "\n")

    for region in REGIONS:
        print(f"{'='*20} PROCESSING {region} {'='*20}")
        price_points: Dict[str, Dict] = {}  # timestamp -> data sources

        try:
            # Historical Dispatch only (no forecasts)
            print(f"  [HISTORICAL] Fetching historical dispatch prices (last {hours_back} hour(s))...")
            historical = fetch_historical_dispatch_all_regions(
                regions=[region],
                hours_back=hours_back,
                force_refresh=force_refresh
            )
            if historical and region in historical:
                for point in historical[region]:
                    ts = point['timestamp']
                    if ts not in price_points:
                        price_points[ts] = {}
                    price_points[ts]['historical_price'] = create_price_record(
                        point['price'],
                        point['source_file'],
                        point.get('fetched_at', datetime.now(AEST).isoformat())
                    )
                print(f"  [OK] {len(historical[region])} historical points")

            # === WRITE TO MONGODB (HISTORICAL ONLY) ===
            print(f"  [SYNC] Writing {len(price_points)} historical records...")
            for ts, sources in price_points.items():
                try:
                    existing = coll.find_one({"region": region, "timestamp": ts})

                    updates: Dict[str, Any] = {"last_updated": datetime.now(AEST).isoformat()}

                    # HISTORICAL: Always replace if new data exists (don't append, replace)
                    if 'historical_price' in sources:
                        new_hist = sources['historical_price']
                        if is_dispatch_file(new_hist['source_file']):
                            # Always replace with new data when available
                            updates['historical_price'] = new_hist
                        else:
                            print(f"  [BLOCKED] Non-dispatch file tried to set historical_price")

                    # Preserve existing forecast data (don't touch it)
                    if existing:
                        if 'dispatch_5min' in existing:
                            updates['dispatch_5min'] = existing['dispatch_5min']
                        if 'dispatch_30min' in existing:
                            updates['dispatch_30min'] = existing['dispatch_30min']
                        if 'Forecast_Price' in existing:
                            updates['Forecast_Price'] = existing['Forecast_Price']
                        # If no new historical_price in updates, preserve existing
                        if 'historical_price' not in updates and existing.get('historical_price'):
                            updates['historical_price'] = existing['historical_price']

                    result = coll.update_one(
                        {"region": region, "timestamp": ts},
                        {"$set": updates},
                        upsert=True
                    )

                    if result.upserted_id:
                        total_inserted += 1
                    elif result.modified_count:
                        total_updated += 1
                    else:
                        total_skipped += 1

                except Exception as e:
                    err = f"{region} {ts}: {e}"
                    errors.append(err)
                    print(f"  [ERROR] {err}")

            print(f"  [DONE] {region} complete\n")

        except Exception as e:
            print(f"  [FATAL] Region {region} failed: {e}")
            errors.append(f"Region {region}: {e}")

    # Summary
    print("="*80)
    print("HISTORICAL SYNC COMPLETE")
    print("="*80)
    print(f"Inserted : {total_inserted}")
    print(f"Updated  : {total_updated}")
    print(f"Skipped  : {total_skipped}")
    print(f"Errors   : {len(errors)}")
    if errors:
        print("\nFirst 10 errors:")
        for e in errors[:10]:
            print(f"  • {e}")

    client.close()
    return len(errors) == 0


# Main sync function
def sync_to_mongodb(force_refresh: bool = False) -> bool:
    client = connect_mongo()
    if not client:
        return False

    db = client[DB_NAME]
    coll = db[COLLECTION_NAME]

    # Indexes
    coll.create_index([("region", 1), ("timestamp", 1)], unique=True)
    coll.create_index("timestamp")
    coll.create_index("region")

    total_inserted = total_updated = total_skipped = 0
    errors: List[str] = []

    print("\n" + "="*80)
    print("NEM PRICE SYNC STARTED - ALL REGIONS")
    print("="*80 + "\n")

    for region in REGIONS:
        print(f"{'='*20} PROCESSING {region} {'='*20}")
        price_points: Dict[str, Dict] = {}  # timestamp -> data sources

        try:
            # 1. Historical Dispatch (actual prices) - HIGHEST PRIORITY
            print(f"  [1/3] Fetching historical dispatch prices...")
            historical = fetch_historical_dispatch_all_regions(
                regions=[region],
                hours_back=8,  # adjust as needed
                force_refresh=force_refresh
            )
            if historical and region in historical:
                for point in historical[region]:
                    ts = point['timestamp']
                    if ts not in price_points:
                        price_points[ts] = {}
                    price_points[ts]['historical_price'] = create_price_record(
                        point['price'],
                        point['source_file'],
                        point.get('fetched_at', datetime.now(AEST).isoformat())
                    )
                print(f"  [OK] {len(historical[region])} historical points")

            # 2. P5MIN (5-minute predispatch)
            print(f"  [2/3] Fetching P5MIN prices...")
            p5 = fetch_p5min_prices(region=region, hours_ahead=2, force_refresh=force_refresh)
            if p5 and p5.get('prices'):
                src = p5['source_file']
                fetched = p5.get('fetched_at', datetime.now(AEST).isoformat())
                for p in p5['prices']:
                    ts = p['timestamp']
                    price_points.setdefault(ts, {})['dispatch_5min'] = create_price_record(p['price'], src, fetched)
                print(f"  [OK] {len(p5['prices'])} P5MIN points")

            # 3. 30-minute Predispatch
            print(f"  [3/3] Fetching predispatch prices...")
            pred = fetch_predispatch_prices(region=region, hours_ahead=2, force_refresh=force_refresh)
            if pred and pred.get('prices'):
                src = pred['source_file']
                fetched = pred.get('fetched_at', datetime.now(AEST).isoformat())
                for p in pred['prices']:
                    ts = p['timestamp']
                    price_points.setdefault(ts, {})['dispatch_30min'] = create_price_record(p['price'], src, fetched)
                print(f"  [OK] {len(pred['prices'])} predispatch points")

            # === WRITE TO MONGODB ===
            print(f"  [SYNC] Writing {len(price_points)} records...")
            for ts, sources in price_points.items():
                try:
                    existing = coll.find_one({"region": region, "timestamp": ts})

                    updates: Dict[str, Any] = {"last_updated": datetime.now(AEST).isoformat()}

                    # HISTORICAL: Only allow real dispatch files
                    if 'historical_price' in sources:
                        if is_dispatch_file(sources['historical_price']['source_file']):
                            updates['historical_price'] = sources['historical_price']
                        else:
                            print(f"  [BLOCKED] Non-dispatch file tried to set historical_price")

                    # Preserve existing real historical price
                    elif existing and existing.get('historical_price'):
                        hist_price = existing['historical_price']
                        if isinstance(hist_price, dict) and is_dispatch_file(hist_price.get('source_file', '')):
                            updates['historical_price'] = hist_price

                    # P5MIN & PREDISPATCH: allow timestamp-based competition
                    for field in ['dispatch_5min', 'dispatch_30min']:
                        if field in sources:
                            new_entry = sources[field]
                            new_ts = new_entry['file_timestamp']

                            if existing and field in existing:
                                existing_field = existing[field]
                                if isinstance(existing_field, dict):
                                    old_ts = parse_file_timestamp(existing_field.get('source_file', '') or "")
                                    if old_ts and new_ts and new_ts <= old_ts:
                                        updates[field] = existing_field
                                        continue
                            updates[field] = new_entry

                    # Final prices
                    full_doc = {**(existing or {}), **updates}
                    updates['Forecast_Price'] = get_forecast_price(full_doc)

                    result = coll.update_one(
                        {"region": region, "timestamp": ts},
                        {"$set": updates},
                        upsert=True
                    )

                    if result.upserted_id:
                        total_inserted += 1
                    elif result.modified_count:
                        total_updated += 1
                    else:
                        total_skipped += 1

                except Exception as e:
                    err = f"{region} {ts}: {e}"
                    errors.append(err)
                    print(f"  [ERROR] {err}")

            print(f"  [DONE] {region} complete\n")

        except Exception as e:
            print(f"  [FATAL] Region {region} failed: {e}")
            errors.append(f"Region {region}: {e}")

    # Cleanup old forecast data (older than 2 hours)
    cleanup_stats = cleanup_old_forecasts(client, max_age_hours=2)

    # Summary
    print("="*80)
    print("SYNC COMPLETE")
    print("="*80)
    print(f"Inserted : {total_inserted}")
    print(f"Updated  : {total_updated}")
    print(f"Skipped  : {total_skipped}")
    print(f"Errors   : {len(errors)}")
    print(f"Cleanup  : {cleanup_stats['documents_updated']} documents updated")
    if errors:
        print("\nFirst 10 errors:")
        for e in errors[:10]:
            print(f"  • {e}")

    client.close()
    return len(errors) == 0


# Entry point
def main():
    force = any(arg in sys.argv for arg in ['--refresh', '-r'])
    clear = any(arg in sys.argv for arg in ['--clear', '-c'])

    if clear:
        if connect_mongo():
            client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
            client[DB_NAME][COLLECTION_NAME].delete_many({})
            client.close()
            print("[OK] Collection cleared")
        force = True

    success = sync_to_mongodb(force_refresh=force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()