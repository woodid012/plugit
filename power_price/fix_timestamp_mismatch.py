"""
Fix documents where settlement timestamp is incorrect relative to file timestamp
Removes historical_price from documents where settlement time is > 5 minutes after file time
"""
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import pytz

# MongoDB connection details
MONGO_USERNAME = "NEMprice"
MONGO_PASSWORD = "test_smart123"
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
DB_NAME = "nem_prices"
COLLECTION_NAME = "price_data"

# Timezone for comparison
AEST_FIXED = pytz.FixedOffset(600)  # UTC+10:00 (AEST)

# Connect to MongoDB
print("Connecting to MongoDB...")
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

print("=" * 80)
print("Fixing timestamp mismatches in MongoDB")
print("=" * 80)

# Find all documents with historical_price
print("Finding documents with historical_price...")
docs_with_historical = collection.find({
    'historical_price': {'$ne': None}
})

fixed_count = 0
skipped_count = 0
error_count = 0

def parse_timestamp_from_filename(filename):
    """Extract timestamp from filename like PUBLIC_DISPATCH_202511191540"""
    if not filename:
        return None
    import re
    match = re.search(r'(\d{12})', filename)
    if match:
        return match.group(1)
    return None

for doc in docs_with_historical:
    try:
        doc_timestamp = doc.get('timestamp')
        hist_price = doc.get('historical_price', {})
        
        if not doc_timestamp or not hist_price or not isinstance(hist_price, dict):
            skipped_count += 1
            continue
        
        # Get file timestamp
        source_file = hist_price.get('source_file', '')
        file_timestamp_str = hist_price.get('file_timestamp', '') or parse_timestamp_from_filename(source_file)
        
        if not file_timestamp_str or len(file_timestamp_str) < 12:
            skipped_count += 1
            continue
        
        # Parse document timestamp (settlement time)
        if isinstance(doc_timestamp, str):
            settlement_dt = datetime.fromisoformat(doc_timestamp.replace('Z', '+00:00'))
        else:
            settlement_dt = doc_timestamp
        
        # Convert to AEST
        if settlement_dt.tzinfo is None:
            settlement_dt = AEST_FIXED.localize(settlement_dt)
        elif settlement_dt.tzinfo != AEST_FIXED:
            settlement_dt = settlement_dt.astimezone(AEST_FIXED)
        
        # Parse file timestamp
        try:
            year = int(file_timestamp_str[0:4])
            month = int(file_timestamp_str[4:6])
            day = int(file_timestamp_str[6:8])
            hour = int(file_timestamp_str[8:10])
            minute = int(file_timestamp_str[10:12])
            file_dt = AEST_FIXED.localize(datetime(year, month, day, hour, minute))
        except Exception as e:
            print(f"Could not parse file timestamp {file_timestamp_str}: {e}")
            skipped_count += 1
            continue
        
        # Check if settlement time is more than 5 minutes after file time
        time_diff = (settlement_dt - file_dt).total_seconds() / 60
        
        if time_diff > 5:
            region = doc.get('region', 'UNKNOWN')
            print(f"Fixing: {region} - settlement {settlement_dt.strftime('%Y-%m-%d %H:%M')} is {time_diff:.1f} min after file {file_dt.strftime('%Y-%m-%d %H:%M')}")
            
            # Remove historical_price
            collection.update_one(
                {'_id': doc['_id']},
                {'$unset': {'historical_price': ''}}
            )
            
            # Recalculate Export_Price
            dispatch_5min = doc.get('dispatch_5min', {})
            dispatch_30min = doc.get('dispatch_30min', {})
            
            p5min_price = dispatch_5min.get('price') if isinstance(dispatch_5min, dict) else None
            predispatch_price = dispatch_30min.get('price') if isinstance(dispatch_30min, dict) else None
            
            new_export_price = p5min_price if p5min_price is not None else predispatch_price
            new_forecast_price = p5min_price if p5min_price is not None else predispatch_price
            
            update_fields = {}
            if new_export_price is not None:
                update_fields['Export_Price'] = new_export_price
            else:
                update_fields['Export_Price'] = None
            
            if new_forecast_price is not None:
                update_fields['Forecast_Price'] = new_forecast_price
            else:
                update_fields['Forecast_Price'] = None
            
            if update_fields:
                collection.update_one(
                    {'_id': doc['_id']},
                    {'$set': update_fields}
                )
            
            fixed_count += 1
        else:
            skipped_count += 1
            
    except Exception as e:
        print(f"Error processing document {doc.get('_id')}: {e}")
        error_count += 1

client.close()

print("=" * 80)
print("Cleanup complete!")
print(f"  Fixed (removed historical_price with timestamp mismatch): {fixed_count}")
print(f"  Skipped (already correct): {skipped_count}")
print(f"  Errors: {error_count}")

