"""
MongoDB Sync for NEMweb Power Prices
Syncs historical, 5-minute, and 30-minute dispatch data to MongoDB for all NEM regions
"""

import sys
import re
from datetime import datetime
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

# Config
MONGO_URI = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
DB_NAME = "nem_prices"
COLLECTION_NAME = "price_data"
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
    return 'PUBLIC_DISPATCH' in filename.upper() and 'LEGACY' in filename.upper()


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


def get_best_price(doc: Dict) -> Optional[float]:
    if doc.get('historical_price'):
        return doc['historical_price']['price']
    if doc.get('dispatch_5min'):
        return doc['dispatch_5min']['price']
    if doc.get('dispatch_30min'):
        return doc['dispatch_30min']['price']
    return None


def get_forecast_price(doc: Dict) -> Optional[float]:
    if doc.get('dispatch_5min'):
        return doc['dispatch_5min']['price']
    if doc.get('dispatch_30min'):
        return doc['dispatch_30min']['price']
    return None


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
            pred = fetch_predispatch_prices(region=region, hours_ahead=48, force_refresh=force_refresh)
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
                        if is_dispatch_file(existing['historical_price'].get('source_file', '')):
                            updates['historical_price'] = existing['historical_price']

                    # P5MIN & PREDISPATCH: allow timestamp-based competition
                    for field in ['dispatch_5min', 'dispatch_30min']:
                        if field in sources:
                            new_entry = sources[field]
                            new_ts = new_entry['file_timestamp']

                            if existing and field in existing:
                                old_ts = parse_file_timestamp(existing[field].get('source_file', '') or "")
                                if old_ts and new_ts and new_ts <= old_ts:
                                    updates[field] = existing[field]
                                    continue
                            updates[field] = new_entry

                    # Final prices
                    full_doc = {**(existing or {}), **updates}
                    updates['Export_Price'] = get_best_price(full_doc)
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

    # Summary
    print("="*80)
    print("SYNC COMPLETE")
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