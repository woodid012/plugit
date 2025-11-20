"""
MongoDB Connection Utilities
Centralized connection logic for MongoDB operations
"""

import sys
from pathlib import Path
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.server_api import ServerApi

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import MongoDB credentials from centralized config
import os
try:
    import importlib
    _ios_logins_module = importlib.import_module('IoS_logins')
    MONGO_URI = _ios_logins_module.MONGO_URI
    DB_NAME = _ios_logins_module.MONGO_DB_NAME
    PRICE_COLLECTION_NAME = _ios_logins_module.MONGO_COLLECTION_NAME
except (ImportError, ModuleNotFoundError):
    # Fallback to environment variables or defaults
    MONGO_URI = os.getenv('MONGO_URI', "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0")
    DB_NAME = os.getenv('MONGO_DB_NAME', "nem_prices")
    PRICE_COLLECTION_NAME = os.getenv('MONGO_COLLECTION_NAME', "price_data")

# Device usage collection name
USAGE_COLLECTION_NAME = "device_usage"


def connect_mongo() -> Optional[MongoClient]:
    """
    Connect to MongoDB and return client
    
    Returns:
        MongoClient instance if successful, None otherwise
    """
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"[ERROR] MongoDB connection failed: {e}")
        return None


def get_db(client: Optional[MongoClient] = None, db_name: Optional[str] = None) -> Optional[Database]:
    """
    Get MongoDB database instance
    
    Args:
        client: MongoClient instance (will create if not provided)
        db_name: Database name (defaults to DB_NAME from config)
        
    Returns:
        Database instance if successful, None otherwise
    """
    if client is None:
        client = connect_mongo()
        if not client:
            return None
    
    db_name = db_name or DB_NAME
    return client[db_name]


def get_collection(
    collection_name: str,
    client: Optional[MongoClient] = None,
    db_name: Optional[str] = None
) -> Optional[Collection]:
    """
    Get MongoDB collection instance
    
    Args:
        collection_name: Name of the collection
        client: MongoClient instance (will create if not provided)
        db_name: Database name (defaults to DB_NAME from config)
        
    Returns:
        Collection instance if successful, None otherwise
    """
    db = get_db(client, db_name)
    if not db:
        return None
    
    return db[collection_name]

