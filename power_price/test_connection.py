"""
Quick test script to verify MongoDB connection
"""
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
    
    # Check if nem_prices database exists
    db = client['nem_prices']
    collections = db.list_collection_names()
    print(f"\nCollections in 'nem_prices' database:")
    if collections:
        for coll in collections:
            count = db[coll].count_documents({})
            print(f"  - {coll}: {count} documents")
    else:
        print("  (no collections yet)")
    
    client.close()
    print("\n✅ Connection test passed! You can now run mongodb_sync.py")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check your internet connection")
    print("2. Verify MongoDB credentials are correct")
    print("3. Check MongoDB Atlas Network Access settings")

