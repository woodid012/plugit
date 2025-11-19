"""
Cleanup script to remove historical_price from future timestamps in MongoDB
This fixes data that was incorrectly stored before the fix was applied
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
AEST = pytz.timezone('Australia/Sydney')
AEST_FIXED = pytz.FixedOffset(600)  # UTC+10:00 (AEST)

# Connect to MongoDB
print("Connecting to MongoDB...")
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# Get current time in AEST
now_aest = datetime.now(AEST)
now_aest_fixed = now_aest.astimezone(AEST_FIXED) if now_aest.tzinfo else AEST_FIXED.localize(now_aest)

print(f"Current time (AEST): {now_aest_fixed.isoformat()}")
print("=" * 80)

# Find all documents with historical_price
print("Finding documents with historical_price...")
docs_with_historical = collection.find({
    'historical_price': {'$ne': None}
})

fixed_count = 0
skipped_count = 0
error_count = 0

for doc in docs_with_historical:
    try:
        doc_timestamp = doc.get('timestamp')
        if not doc_timestamp:
            skipped_count += 1
            continue
        
        # Parse timestamp
        if isinstance(doc_timestamp, str):
            price_dt = datetime.fromisoformat(doc_timestamp.replace('Z', '+00:00'))
        else:
            price_dt = doc_timestamp
        
        # Convert to AEST for comparison
        if price_dt.tzinfo is None:
            price_dt = AEST_FIXED.localize(price_dt)
        elif price_dt.tzinfo != AEST_FIXED:
            price_dt = price_dt.astimezone(AEST_FIXED)
        
        # Check if timestamp is in the future
        is_future = price_dt >= now_aest_fixed
        
        if is_future:
            # Remove historical_price from future timestamps
            region = doc.get('region', 'UNKNOWN')
            print(f"Fixing: {region} at {doc_timestamp} - removing historical_price (future timestamp)")
            
            # Update document to remove historical_price
            collection.update_one(
                {'_id': doc['_id']},
                {'$unset': {'historical_price': ''}}
            )
            
            # Recalculate Export_Price (it should use forecast data now)
            # Get other price sources
            dispatch_5min = doc.get('dispatch_5min', {})
            dispatch_30min = doc.get('dispatch_30min', {})
            
            p5min_price = dispatch_5min.get('price') if isinstance(dispatch_5min, dict) else None
            predispatch_price = dispatch_30min.get('price') if isinstance(dispatch_30min, dict) else None
            
            # Calculate new Export_Price (historical is None now, so use p5min or predispatch)
            new_export_price = p5min_price if p5min_price is not None else predispatch_price
            
            # Calculate Forecast_Price
            new_forecast_price = p5min_price if p5min_price is not None else predispatch_price
            
            # Update Export_Price and Forecast_Price
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
print(f"  Fixed (removed historical_price from future): {fixed_count}")
print(f"  Skipped (already correct): {skipped_count}")
print(f"  Errors: {error_count}")

