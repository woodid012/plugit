"""
Fetch actual dispatch price data from NEMWeb Dispatch Reports

Scans the latest dispatch report, extracts RRP for regions (NSW1, VIC1, etc.),
and stores as historical_price in MongoDB.

This script focuses ONLY on actual/historical dispatch data.
"""

import os
import re
import csv
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import pytz
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure

# NEMweb URLs
DISPATCH_REPORTS_URL = "https://nemweb.com.au/Reports/Current/Dispatch_Reports/"

# Timezone definitions
AEST_FIXED = pytz.FixedOffset(600)  # UTC+10:00 (AEST)
AEST = pytz.timezone('Australia/Sydney')

# MongoDB connection details
MONGO_USERNAME = "NEMprice"
MONGO_PASSWORD = "test_smart123"
MONGO_URI = f"mongodb+srv://{MONGO_USERNAME}:{MONGO_PASSWORD}@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
DB_NAME = "nem_prices"
COLLECTION_NAME = "price_data"

# Regions to extract (NSW1, VIC1, and others)
REGIONS = ['NSW1', 'VIC1', 'QLD1', 'SA1', 'TAS1']

def get_latest_dispatch_file() -> Optional[tuple]:
    """
    Scan the dispatch reports directory and find the latest file.
    Returns tuple of (url, settlement_timestamp) or None.
    Settlement timestamp is extracted from filename (e.g., PUBLIC_DISPATCH_202511191720 -> 202511191720)
    """
    try:
        print(f"[INFO] Scanning {DISPATCH_REPORTS_URL}...")
        
        headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache'
        }
        
        response = requests.get(DISPATCH_REPORTS_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pattern to match dispatch files: PUBLIC_DISPATCH_YYYYMMDDHHMM_...
        pattern = r'PUBLIC_DISPATCH_(\d{12})_'
        files = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(pattern, href)
            if match:
                settlement_timestamp = match.group(1)  # YYYYMMDDHHMM
                
                # Build full URL
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(DISPATCH_REPORTS_URL)
                    url = f"{parsed.scheme}://{parsed.netloc}{href}"
                else:
                    url = DISPATCH_REPORTS_URL.rstrip('/') + '/' + href
                
                files.append((settlement_timestamp, url))
        
        if not files:
            print("[ERROR] No dispatch files found")
            return None
        
        # Sort by timestamp (most recent first)
        files.sort(reverse=True)
        latest_timestamp, latest_url = files[0]
        
        print(f"[OK] Found latest file: PUBLIC_DISPATCH_{latest_timestamp}_...")
        print(f"[INFO] Settlement period: {latest_timestamp}")
        
        return (latest_url, latest_timestamp)
        
    except Exception as e:
        print(f"[ERROR] Failed to scan dispatch reports: {e}")
        import traceback
        traceback.print_exc()
        return None

def parse_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """
    Parse settlement timestamp from filename.
    Example: PUBLIC_DISPATCH_202511191720 -> 2025-11-19 17:20:00
    Returns datetime in AEST timezone.
    """
    match = re.search(r'(\d{12})', filename)
    if match:
        timestamp_str = match.group(1)
        try:
            year = int(timestamp_str[0:4])
            month = int(timestamp_str[4:6])
            day = int(timestamp_str[6:8])
            hour = int(timestamp_str[8:10])
            minute = int(timestamp_str[10:12])
            dt = datetime(year, month, day, hour, minute, 0)
            return AEST_FIXED.localize(dt)
        except (ValueError, IndexError) as e:
            print(f"[WARNING] Could not parse timestamp from filename {filename}: {e}")
            return None
    return None

def download_and_extract_zip(url: str) -> Optional[tempfile.TemporaryDirectory]:
    """Download ZIP file and extract to temporary directory"""
    try:
        print(f"[INFO] Downloading {url}...")
        
        headers = {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache'
        }
        
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        temp_dir = tempfile.TemporaryDirectory()
        zip_path = os.path.join(temp_dir.name, 'data.zip')
        
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir.name)
        
        print(f"[OK] Extracted to {temp_dir.name}")
        return temp_dir
        
    except Exception as e:
        print(f"[ERROR] Failed to download/extract ZIP: {e}")
        import traceback
        traceback.print_exc()
        return None

def find_csv_file(directory: str) -> Optional[str]:
    """Find the main CSV file in the extracted directory"""
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.CSV') or file.endswith('.csv'):
                return os.path.join(root, file)
    return None

def parse_dispatch_csv(csv_path: str, expected_settlement_date: datetime, 
                       regions: List[str] = None) -> Dict[str, Dict]:
    """
    Parse dispatch CSV file and extract RRP for specified regions.
    
    Args:
        csv_path: Path to CSV file
        expected_settlement_date: Expected settlement date from filename
        regions: List of regions to extract (default: ['NSW1', 'VIC1'])
    
    Returns:
        Dictionary mapping region -> {'timestamp': iso_string, 'price': float}
    """
    if regions is None:
        regions = ['NSW1', 'VIC1']
    
    results = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            column_headers = None
            regionid_idx = None
            datetime_idx = None
            rrp_idx = None
            
            for line in f:
                parts = line.strip().split(',')
                
                if not parts:
                    continue
                
                row_type = parts[0]
                
                # Header row for DREGION table
                if row_type == 'I' and len(parts) > 2 and parts[1] == 'DREGION':
                    column_headers = [col.strip() for col in parts[4:]]
                    
                    try:
                        regionid_idx = column_headers.index('REGIONID')
                        datetime_idx = column_headers.index('SETTLEMENTDATE')
                        rrp_idx = column_headers.index('RRP')
                        print(f"[INFO] Found DREGION table with {len(column_headers)} columns")
                    except ValueError as e:
                        print(f"[ERROR] Missing required column: {e}")
                        return {}
                
                # Data row for DREGION table
                elif row_type == 'D' and len(parts) > 2 and parts[1] == 'DREGION' and column_headers:
                    values = parts[4:]
                    
                    if len(values) <= max(regionid_idx, datetime_idx, rrp_idx):
                        continue
                    
                    try:
                        row_region = values[regionid_idx].strip()
                        dt_str = values[datetime_idx].strip().strip('"')
                        price_str = values[rrp_idx].strip()
                        
                        # Filter by region
                        if row_region not in regions:
                            continue
                        
                        # Parse datetime
                        dt = None
                        for fmt in ['%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M',
                                   '%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S',
                                   '%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M']:
                            try:
                                dt = datetime.strptime(dt_str, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if dt is None:
                            print(f"[WARNING] Could not parse datetime: {dt_str}")
                            continue
                        
                        # Localize to AEST
                        dt_local = AEST_FIXED.localize(dt)
                        
                        # Validate settlement date matches filename timestamp
                        time_diff_seconds = abs((dt_local - expected_settlement_date).total_seconds())
                        if time_diff_seconds > 60:  # More than 1 minute difference
                            print(f"[WARNING] Settlement date mismatch for {row_region}: "
                                  f"CSV has {dt_local.strftime('%d/%m/%Y %H:%M:%S')}, "
                                  f"filename expects {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')} "
                                  f"(difference: {time_diff_seconds:.0f} seconds) - SKIPPING")
                            continue
                        
                        # Use expected date from filename for consistency
                        if time_diff_seconds > 0:
                            dt_local = expected_settlement_date
                        
                        # Parse price
                        price = float(price_str)
                        
                        # Store result for this region
                        results[row_region] = {
                            'timestamp': dt_local.isoformat(),
                            'price': round(price, 2)
                        }
                        
                        print(f"[OK] {row_region}: RRP = {price:.5f} at {dt_local.strftime('%d/%m/%Y %H:%M:%S')}")
                        
                    except (ValueError, IndexError) as e:
                        print(f"[WARNING] Error parsing row: {e}")
                        continue
        
        return results
        
    except Exception as e:
        print(f"[ERROR] Failed to parse CSV: {e}")
        import traceback
        traceback.print_exc()
        return {}

def connect_mongodb() -> Optional[MongoClient]:
    """Connect to MongoDB and return client"""
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("[OK] Successfully connected to MongoDB!")
        return client
    except ConnectionFailure as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] MongoDB connection error: {e}")
        return None

def store_to_mongodb(region: str, timestamp: str, price: float, source_file: str):
    """
    Store historical price data to MongoDB.
    Updates the historical_price field for the given region and timestamp.
    """
    client = connect_mongodb()
    if not client:
        return False
    
    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Create indexes if they don't exist
        collection.create_index([("region", 1), ("timestamp", 1)], unique=True)
        
        # Prepare document
        now = datetime.now(AEST)
        
        # Get existing document or create new one
        existing_doc = collection.find_one({
            'region': region,
            'timestamp': timestamp
        })
        
        # VALIDATION: Only allow dispatch report files to write to historical_price
        # Reject predispatch and p5min files
        if source_file:
            source_upper = source_file.upper()
            if 'PUBLIC_PREDISPATCH' in source_upper or 'PUBLIC_P5MIN' in source_upper or 'P5MIN' in source_upper or 'PREDISPATCH' in source_upper:
                print(f"[ERROR] REJECTED: Source file '{source_file}' is from predispatch/p5min, not dispatch. "
                      f"Cannot write to historical_price field.")
                client.close()
                return False
            elif 'PUBLIC_DISPATCH' not in source_upper:
                print(f"[ERROR] REJECTED: Source file '{source_file}' is not a recognized dispatch file. "
                      f"Cannot write to historical_price field.")
                client.close()
                return False
        
        # Prepare historical_price data
        historical_price_data = {
            'price': price,
            'source_file': source_file,
            'file_timestamp': parse_timestamp_from_filename(source_file).strftime('%Y%m%d%H%M') if parse_timestamp_from_filename(source_file) else '',
            'fetched_at': now.isoformat()
        }
        
        # Update document
        update_doc = {
            'region': region,
            'timestamp': timestamp,
            'historical_price': historical_price_data,
            'last_updated': now.isoformat()
        }
        
        # If document exists, preserve other fields
        if existing_doc:
            # Keep dispatch_5min and dispatch_30min if they exist
            if 'dispatch_5min' in existing_doc:
                update_doc['dispatch_5min'] = existing_doc['dispatch_5min']
            if 'dispatch_30min' in existing_doc:
                update_doc['dispatch_30min'] = existing_doc['dispatch_30min']
            
            # Clean up existing historical_price if it has predispatch/p5min files
            existing_hist = existing_doc.get('historical_price')
            if existing_hist and isinstance(existing_hist, dict):
                existing_source = existing_hist.get('source_file', '')
                if existing_source:
                    # Check if existing source_file contains predispatch/p5min files
                    if ',' in existing_source:
                        files = [f.strip() for f in existing_source.split(',')]
                        dispatch_files = [f for f in files if 'PUBLIC_DISPATCH' in f.upper()]
                        if dispatch_files:
                            # Clean up to only dispatch files
                            historical_price_data['source_file'] = ', '.join(dispatch_files)
                        # If no dispatch files, we'll overwrite with the new dispatch file
                    elif 'PUBLIC_PREDISPATCH' in existing_source.upper() or 'PUBLIC_P5MIN' in existing_source.upper():
                        # Existing file is predispatch/p5min - we'll overwrite with dispatch file
                        pass
        
        # Upsert document
        result = collection.update_one(
            {'region': region, 'timestamp': timestamp},
            {'$set': update_doc},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"[OK] Inserted historical_price for {region} at {timestamp}")
        else:
            print(f"[OK] Updated historical_price for {region} at {timestamp}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to store to MongoDB: {e}")
        import traceback
        traceback.print_exc()
        client.close()
        return False

def fetch_historical_dispatch_all_regions(
    regions: List[str] = None,
    hours_back: int = 8,
    force_refresh: bool = False
) -> Dict[str, List[Dict]]:
    """
    Compatibility function for mongodb_sync.py
    Fetches historical dispatch prices and returns in the format expected by mongodb_sync.py
    Returns: {region: [{"timestamp": "...", "price": ..., "source_file": "...", "fetched_at": "..."}, ...]}
    """
    if regions is None:
        regions = REGIONS
    
    # Get latest dispatch file
    result = get_latest_dispatch_file()
    if not result:
        print("[ERROR] Could not find latest dispatch file")
        return {}
    
    url, settlement_timestamp = result
    source_filename = os.path.basename(url)
    
    # Parse expected settlement date from filename
    expected_settlement_date = parse_timestamp_from_filename(source_filename)
    if not expected_settlement_date:
        print(f"[ERROR] Could not parse settlement date from filename: {source_filename}")
        return {}
    
    # Download and extract
    temp_dir = download_and_extract_zip(url)
    if not temp_dir:
        print("[ERROR] Failed to download/extract ZIP file")
        return {}
    
    try:
        # Find and parse CSV
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return {}
        
        # Parse CSV
        results = parse_dispatch_csv(csv_path, expected_settlement_date, regions=regions)
        
        if not results:
            print("[WARNING] No price data extracted")
            return {}
        
        # Convert to format expected by mongodb_sync.py
        all_results: Dict[str, List[Dict]] = {r: [] for r in regions}
        fetched_at = datetime.now(AEST).isoformat()
        
        for region, data in results.items():
            point = {
                'timestamp': data['timestamp'],
                'price': data['price'],
                'source_file': source_filename,
                'fetched_at': fetched_at
            }
            all_results[region].append(point)
        
        return all_results
        
    finally:
        temp_dir.cleanup()

def main():
    """
    Main function: fetch latest dispatch report and store historical prices
    """
    print("=" * 80)
    print("NEMWeb Dispatch Historical Price Fetcher")
    print("=" * 80)
    print()
    
    # Step 1: Get latest dispatch file
    print("[1/4] Finding latest dispatch report...")
    result = get_latest_dispatch_file()
    if not result:
        print("[ERROR] Could not find latest dispatch file")
        return False
    
    url, settlement_timestamp = result
    source_filename = os.path.basename(url)
    
    # Parse expected settlement date from filename
    expected_settlement_date = parse_timestamp_from_filename(source_filename)
    if not expected_settlement_date:
        print(f"[ERROR] Could not parse settlement date from filename: {source_filename}")
        return False
    
    print(f"[INFO] Expected settlement date: {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # Step 2: Download and extract
    print("[2/4] Downloading and extracting ZIP file...")
    temp_dir = download_and_extract_zip(url)
    if not temp_dir:
        print("[ERROR] Failed to download/extract ZIP file")
        return False
    
    try:
        # Step 3: Find and parse CSV
        print("[3/4] Finding CSV file...")
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return False
        
        print(f"[OK] Found CSV: {os.path.basename(csv_path)}")
        print()
        
        print("[4/4] Parsing CSV for DREGION data...")
        print(f"[INFO] Looking for regions: {', '.join(REGIONS)}")
        print(f"[INFO] Checking SETTLEMENTDATE matches: {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')}")
        print()
        
        # Parse CSV
        results = parse_dispatch_csv(csv_path, expected_settlement_date, regions=REGIONS)
        
        if not results:
            print("[WARNING] No price data extracted")
            return False
        
        print()
        print("=" * 80)
        print("STORING TO MONGODB")
        print("=" * 80)
        
        # Step 4: Store to MongoDB
        success_count = 0
        for region, data in results.items():
            if store_to_mongodb(region, data['timestamp'], data['price'], source_filename):
                success_count += 1
        
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Regions processed: {success_count}/{len(results)}")
        print(f"Source file: {source_filename}")
        print(f"Settlement period: {settlement_timestamp}")
        print()
        
        for region, data in results.items():
            print(f"  {region}: RRP = {data['price']:.5f} at {data['timestamp']}")
        
        print()
        print("[SUCCESS] Historical price data stored to MongoDB!")
        return True
        
    finally:
        # Cleanup
        temp_dir.cleanup()
        print("[OK] Cleaned up temporary files")

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
