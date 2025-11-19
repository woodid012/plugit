# Testing MongoDB Sync

## Step 1: Install Dependencies

First, make sure you have all required packages installed:

```bash
pip install -r power_price/requirements.txt
```

Or install pymongo specifically:
```bash
pip install pymongo>=4.6.0
```

## Step 2: Test MongoDB Connection

You can test the MongoDB connection first with a simple script:

```python
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("✅ Successfully connected to MongoDB!")
    
    # List databases
    print("\nAvailable databases:")
    for db_name in client.list_database_names():
        print(f"  - {db_name}")
    
    client.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
```

Save this as `test_connection.py` and run:
```bash
python test_connection.py
```

## Step 3: Run the Sync Script

### Option A: Test with a Single Region (Quick Test)

First, let's modify the script temporarily to test with just one region. You can edit `mongodb_sync.py` and change:

```python
NEM_REGIONS = ['VIC1']  # Test with just one region first
```

Then run:
```bash
cd power_price
python mongodb_sync.py
```

### Option B: Run Full Sync

For all regions:
```bash
cd power_price
python mongodb_sync.py
```

### Option C: Force Refresh (Re-fetch Everything)

```bash
cd power_price
python mongodb_sync.py --refresh
```

## Step 4: Verify Data in MongoDB

### Using MongoDB Compass (GUI)

1. Download MongoDB Compass: https://www.mongodb.com/products/compass
2. Connect using connection string:
   ```
   mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0
   ```
3. Navigate to `nem_prices` database → `price_data` collection
4. Browse documents and verify:
   - Documents have `region`, `timestamp`, `Export_Price`
   - Historical, dispatch_5min, dispatch_30min fields are populated
   - File timestamps are present

### Using Python Script

Create a file `verify_data.py`:

```python
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

uri = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))

db = client['nem_prices']
collection = db['price_data']

# Count documents
total = collection.count_documents({})
print(f"Total documents: {total}")

# Count by region
print("\nDocuments by region:")
for region in ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']:
    count = collection.count_documents({'region': region})
    print(f"  {region}: {count}")

# Show a sample document
print("\nSample document:")
sample = collection.find_one()
if sample:
    import json
    print(json.dumps(sample, indent=2, default=str))

# Check Export_Price calculation
print("\nExport_Price statistics:")
with_export = collection.count_documents({'Export_Price': {'$ne': None}})
print(f"  Documents with Export_Price: {with_export}")

# Latest timestamps by region
print("\nLatest timestamps by region:")
for region in ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']:
    latest = collection.find_one(
        {'region': region},
        sort=[('timestamp', -1)]
    )
    if latest:
        print(f"  {region}: {latest.get('timestamp')} (Export_Price: {latest.get('Export_Price')})")

client.close()
```

Run:
```bash
python verify_data.py
```

## Step 5: Check for Errors

The sync script will output:
- `[OK]` messages for successful operations
- `[ERROR]` messages for failures
- `[WARNING]` messages for issues that don't stop execution
- A summary at the end showing:
  - Total inserted
  - Total updated
  - Total skipped
  - Errors count

## Troubleshooting

### Connection Issues
- Verify your internet connection
- Check MongoDB credentials are correct
- Ensure MongoDB Atlas allows connections from your IP (check Network Access in Atlas)

### No Data Fetched
- Check NEMweb is accessible: https://nemweb.com.au/Reports/Current/
- Verify the fetch_prices.py module works independently
- Try running with `--refresh` flag

### Import Errors
- Make sure you're running from the correct directory
- Try: `python -m power_price.mongodb_sync` from project root
- Or: `cd power_price && python mongodb_sync.py`

### Data Not Updating
- Check file timestamps in source_file fields
- Verify the update logic is working (check skipped count)
- Try force refresh: `python mongodb_sync.py --refresh`

## Expected Output

When running successfully, you should see:
```
================================================================================
MongoDB NEMweb Price Data Sync
================================================================================
[OK] Successfully connected to MongoDB!
[OK] Database indexes created/verified

================================================================================
Processing region: VIC1
================================================================================

[1/3] Fetching historical dispatch prices for VIC1...
[OK] Fetched X historical price points

[2/3] Fetching 5-minute predispatch for VIC1...
[OK] Fetched X 5-minute price points

[3/3] Fetching 30-minute predispatch for VIC1...
[OK] Fetched X 30-minute price points

[SYNC] Syncing X price points to MongoDB...
[OK] Region VIC1: X price points processed

... (repeats for each region)

================================================================================
SYNC SUMMARY
================================================================================
Total inserted: X
Total updated: X
Total skipped (older data): X
Errors: 0

[OK] MongoDB sync completed!
```

