"""
Check a specific timestamp in MongoDB to see how it's stored
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

# Connect to MongoDB
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# Check for VIC1, 19/11/25 5:25 AEST
# AEST is UTC+10, so 5:25 AEST = 19:25 UTC (previous day)
# But we need to be careful about the date - 19/11/25 could be November 19, 2025
# Let's check around that time

region = "VIC1"
target_date = "2025-11-19T05:25:00+10:00"  # 5:25 AEST on Nov 19, 2025

print(f"Checking for timestamp: {target_date}")
print(f"Region: {region}")
print("=" * 80)

# Query MongoDB
doc = collection.find_one({
    'region': region,
    'timestamp': target_date
})

if doc:
    print("[OK] Found document in database!")
    print("\nDocument contents:")
    print("-" * 80)
    
    # Remove _id for cleaner output
    doc.pop('_id', None)
    
    import json
    print(json.dumps(doc, indent=2, default=str))
    
    print("\n" + "=" * 80)
    print("Analysis:")
    print("-" * 80)
    
    # Check what's in historical_price
    hist_price = doc.get('historical_price')
    if hist_price:
        print(f"[OK] historical_price exists: {hist_price.get('price')}")
        print(f"  Source file: {hist_price.get('source_file', 'N/A')}")
        print(f"  File timestamp: {hist_price.get('file_timestamp', 'N/A')}")
        print(f"  Fetched at: {hist_price.get('fetched_at', 'N/A')}")
    else:
        print("[X] No historical_price field")
    
    # Check other price fields
    dispatch_5min = doc.get('dispatch_5min')
    if dispatch_5min:
        print(f"\n[OK] dispatch_5min exists: {dispatch_5min.get('price')}")
    
    dispatch_30min = doc.get('dispatch_30min')
    if dispatch_30min:
        print(f"\n[OK] dispatch_30min exists: {dispatch_30min.get('price')}")
    
    forecast_price = doc.get('Forecast_Price')
    if forecast_price:
        print(f"\n[OK] Forecast_Price exists: {forecast_price}")
    
    export_price = doc.get('Export_Price')
    if export_price:
        print(f"\n[OK] Export_Price exists: {export_price}")
    
    # Check if timestamp is in the past
    doc_timestamp = doc.get('timestamp')
    if doc_timestamp:
        try:
            if isinstance(doc_timestamp, str):
                doc_dt = datetime.fromisoformat(doc_timestamp.replace('Z', '+00:00'))
            else:
                doc_dt = doc_timestamp
            
            now = datetime.now(pytz.timezone('Australia/Sydney'))
            is_past = doc_dt < now
            
            print(f"\n" + "=" * 80)
            print(f"Timestamp check:")
            print(f"  Document timestamp: {doc_timestamp}")
            print(f"  Current time (AEDT): {now.isoformat()}")
            print(f"  Is in the past: {is_past}")
            
            if hist_price and not is_past:
                print(f"\n[WARNING] historical_price exists for a FUTURE timestamp!")
                print(f"   This is the database issue - future data is being stored as historical_price")
        except Exception as e:
            print(f"\nError checking timestamp: {e}")
    
else:
    print("[X] Document not found in database")
    
    # Try to find nearby timestamps
    print("\nSearching for nearby timestamps...")
    
    # Try a few variations
    variations = [
        "2025-11-19T05:25:00+11:00",  # AEDT
        "2025-11-19T05:20:00+10:00",  # 5:20 AEST
        "2025-11-19T05:30:00+10:00",  # 5:30 AEST
    ]
    
    for var in variations:
        nearby = collection.find_one({
            'region': region,
            'timestamp': var
        })
        if nearby:
            print(f"  Found nearby: {var}")
            print(f"    historical_price: {nearby.get('historical_price', {}).get('price', 'N/A') if nearby.get('historical_price') else 'N/A'}")
            break

client.close()

