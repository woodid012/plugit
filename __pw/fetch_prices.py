"""
NEMweb Power Price Data Fetcher
Downloads and caches electricity price data from NEMweb for VIC1 region
"""

import os
import re
import json
import csv
import zipfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import pytz

# NEMweb URLs
P5_REPORTS_URL = "https://nemweb.com.au/Reports/Current/P5_Reports/"  # Latest 5-minute predispatch
PREDISPATCH_REPORTS_URL = "https://nemweb.com.au/Reports/Current/Predispatch_Reports/"  # Full predispatch forecasts
DISPATCH_REPORTS_URL = "https://nemweb.com.au/Reports/Current/Dispatch_Reports/"  # Historical dispatch prices

# Legacy URLs (kept for reference)
PUBLIC_PRICES_URL = "https://nemweb.com.au/Reports/Current/Public_Prices/"
PREDISPATCH_IRSR_URL = "https://nemweb.com.au/Reports/Current/Predispatch_IRSR/"
CURRENT_DISPATCH_URL = "https://nemweb.com.au/Reports/Current/DispatchIS/"

# Timezone definitions
AEST = pytz.timezone('Australia/Sydney')  # This will handle AEST/AEDT automatically
UTC = pytz.UTC

# Cache directory (same as script directory)
CACHE_DIR = Path(__file__).parent


def get_latest_file_url(base_url: str, pattern: str = r'PUBLIC_PRICES_(\d{8})\d{4}') -> Optional[tuple]:
    """
    Parse HTML directory listing to find the most recent file by date (YYYYMMDD)
    Returns tuple of (url, date_string) or None
    """
    try:
        response = requests.get(base_url, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links matching the pattern
        latest_date = None
        latest_url = None
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(pattern, href)
            if match:
                date_str = match.group(1)  # YYYYMMDD

                # Check if this is the latest date
                if latest_date is None or date_str > latest_date:
                    latest_date = date_str
                    # Handle both absolute and relative URLs
                    if href.startswith('http'):
                        latest_url = href
                    elif href.startswith('/'):
                        # Extract base domain from base_url
                        from urllib.parse import urlparse
                        parsed = urlparse(base_url)
                        latest_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                    else:
                        latest_url = base_url.rstrip('/') + '/' + href
        
        if latest_url and latest_date:
            print(f"[INFO] Found latest file: {latest_date}")
            return (latest_url, latest_date)
        else:
            print("[WARNING] No matching files found")
            return None
            
    except Exception as e:
        print(f"[ERROR] Failed to fetch directory listing: {e}")
        return None


def download_and_extract_zip(url: str) -> Optional[tempfile.TemporaryDirectory]:
    """
    Download ZIP file and extract to temporary directory
    Returns TemporaryDirectory object or None
    """
    try:
        print(f"[INFO] Downloading {url}...")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Create temporary directory
        temp_dir = tempfile.TemporaryDirectory()
        
        # Save ZIP to temp file
        zip_path = os.path.join(temp_dir.name, 'data.zip')
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir.name)
        
        print(f"[OK] Extracted to {temp_dir.name}")
        return temp_dir
        
    except Exception as e:
        print(f"[ERROR] Failed to download/extract ZIP: {e}")
        return None


def find_csv_file(directory: str) -> Optional[str]:
    """
    Find the main CSV file in the extracted directory
    """
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.CSV') or file.endswith('.csv'):
                # Prefer files with 'PREDISPATCH' or 'IRSR' in name
                if 'PREDISPATCH' in file.upper() or 'IRSR' in file.upper():
                    return os.path.join(root, file)
    
    # If no preferred file found, return first CSV
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.CSV') or file.endswith('.csv'):
                return os.path.join(root, file)
    
    return None


def parse_price_csv(csv_path: str, region: str = 'VIC1', hours_ahead: int = 12, hours_back: int = 0) -> List[Dict]:
    """
    Parse NEMweb PUBLIC_PRICES CSV file and extract price data for specified region
    Returns list of {timestamp, price} dictionaries

    The CSV has a special format with multiple table types:
    - Line starting with 'C': Metadata header
    - Line starting with 'I': Table column headers (format: I,TABLE_NAME,SUBTYPE,VERSION,COL1,COL2,...)
    - Lines starting with 'D': Data rows (format: D,TABLE_NAME,SUBTYPE,VERSION,val1,val2,...)
    """
    prices = []

    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Get current time in AEST/AEDT (timezone-aware)
            now_local = datetime.now(AEST)
            cutoff_future = now_local + timedelta(hours=hours_ahead)
            cutoff_past = now_local - timedelta(hours=hours_back)

            # Parse the special NEMweb CSV format
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
                    # Column names start at index 4 (after I, DREGION, , VERSION)
                    column_headers = [col.strip() for col in parts[4:]]

                    # Find column indices
                    try:
                        regionid_idx = column_headers.index('REGIONID')
                        datetime_idx = column_headers.index('SETTLEMENTDATE')
                        rrp_idx = column_headers.index('RRP')
                        print(f"[INFO] Found DREGION table with {len(column_headers)} columns")
                    except ValueError as e:
                        print(f"[ERROR] Missing required column: {e}")
                        return []

                # Data row for DREGION table
                elif row_type == 'D' and len(parts) > 2 and parts[1] == 'DREGION' and column_headers:
                    # Data values start at index 4 (after D, DREGION, , VERSION)
                    values = parts[4:]

                    if len(values) <= max(regionid_idx, datetime_idx, rrp_idx):
                        continue

                    try:
                        # Extract values
                        row_region = values[regionid_idx].strip()
                        dt_str = values[datetime_idx].strip().strip('"')
                        price_str = values[rrp_idx].strip()

                        # Filter by region
                        if row_region != region:
                            continue

                        # Parse datetime
                        dt = None
                        for fmt in ['%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S',
                                   '%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M']:
                            try:
                                dt = datetime.strptime(dt_str, fmt)
                                break
                            except ValueError:
                                continue

                        if dt is None:
                            continue

                        # Localize to Australian timezone (handles AEST/AEDT automatically)
                        dt_local = AEST.localize(dt)

                        # Filter by time range
                        # Include data within the specified time window (past or future)
                        if hours_back > 0:
                            # Historical mode: include data from past
                            if dt_local < cutoff_past or dt_local > now_local:
                                continue
                        elif hours_ahead > 0:
                            # Future mode: include only future data
                            if dt_local <= now_local or dt_local > cutoff_future:
                                continue
                        else:
                            # No filtering if both are 0
                            pass

                        # Parse price
                        price = float(price_str)

                        prices.append({
                            'timestamp': dt_local.isoformat(),
                            'price': round(price, 2)
                        })

                    except (ValueError, IndexError) as e:
                        # Skip problematic rows
                        continue

            # Sort by timestamp
            prices.sort(key=lambda x: x['timestamp'])

            print(f"[OK] Extracted {len(prices)} price points for {region}")
            return prices

    except Exception as e:
        print(f"[ERROR] Failed to parse CSV: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_region_csv(csv_path: str, region: str = 'VIC1', table_name: str = 'DREGION',
                     hours_ahead: int = 12, hours_back: int = 0) -> List[Dict]:
    """
    Generic parser for regional price data from NEMweb CSV files
    Handles DREGION (dispatch), PDREGION (predispatch), and P5MIN_REGIONSOLUTION (5-min predispatch)

    Returns list of {timestamp, price} dictionaries
    """
    prices = []

    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Get current time in AEST/AEDT (timezone-aware)
            now_local = datetime.now(AEST)
            cutoff_future = now_local + timedelta(hours=hours_ahead)
            cutoff_past = now_local - timedelta(hours=hours_back)

            # Parse the special NEMweb CSV format
            column_headers = None
            regionid_idx = None
            datetime_idx = None
            rrp_idx = None

            for line in f:
                parts = line.strip().split(',')

                if not parts:
                    continue

                row_type = parts[0]

                # Header row for target table
                if row_type == 'I' and len(parts) > 2 and parts[1].upper() in [table_name.upper(), table_name.split('_')[0].upper()]:
                    # Column names start at index 4 (after I, TABLE_NAME, , VERSION)
                    column_headers = [col.strip() for col in parts[4:]]

                    # Find column indices
                    try:
                        # Look for REGIONID column
                        regionid_idx = column_headers.index('REGIONID') if 'REGIONID' in column_headers else None

                        # Look for datetime column (different names in different reports)
                        datetime_idx = None
                        for col_name in ['SETTLEMENTDATE', 'PERIODID', 'INTERVAL_DATETIME']:
                            if col_name in column_headers:
                                datetime_idx = column_headers.index(col_name)
                                break

                        # Look for price column
                        rrp_idx = column_headers.index('RRP') if 'RRP' in column_headers else None

                        if regionid_idx is not None and datetime_idx is not None and rrp_idx is not None:
                            print(f"[INFO] Found {parts[1]} table with {len(column_headers)} columns")
                        else:
                            continue

                    except ValueError as e:
                        continue

                # Data row for target table
                elif row_type == 'D' and len(parts) > 2 and column_headers and regionid_idx is not None:
                    table_prefix = parts[1].upper()
                    if table_prefix not in [table_name.upper(), table_name.split('_')[0].upper()]:
                        continue

                    # Data values start at index 4 (after D, TABLE_NAME, , VERSION)
                    values = parts[4:]

                    if len(values) <= max(regionid_idx, datetime_idx, rrp_idx):
                        continue

                    try:
                        # Extract values
                        row_region = values[regionid_idx].strip()
                        dt_str = values[datetime_idx].strip().strip('"')
                        price_str = values[rrp_idx].strip()

                        # Filter by region
                        if row_region != region:
                            continue

                        # Parse datetime
                        dt = None
                        for fmt in ['%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S',
                                   '%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M']:
                            try:
                                dt = datetime.strptime(dt_str, fmt)
                                break
                            except ValueError:
                                continue

                        if dt is None:
                            continue

                        # Localize to Australian timezone (handles AEST/AEDT automatically)
                        dt_local = AEST.localize(dt)

                        # Filter by time range
                        # Include data within the specified time window (past or future)
                        if hours_back > 0:
                            # Historical mode: include data from past
                            if dt_local < cutoff_past or dt_local > now_local:
                                continue
                        elif hours_ahead > 0:
                            # Future mode: include only future data
                            if dt_local <= now_local or dt_local > cutoff_future:
                                continue
                        else:
                            # No filtering if both are 0
                            pass

                        # Parse price
                        price = float(price_str)

                        prices.append({
                            'timestamp': dt_local.isoformat(),
                            'price': round(price, 2)
                        })

                    except (ValueError, IndexError) as e:
                        # Skip problematic rows
                        continue

            # Sort by timestamp
            prices.sort(key=lambda x: x['timestamp'])

            print(f"[OK] Extracted {len(prices)} price points for {region}")
            return prices

    except Exception as e:
        print(f"[ERROR] Failed to parse CSV: {e}")
        import traceback
        traceback.print_exc()
        return []


def save_to_json(data: Dict, filename: str):
    """
    Save data to JSON file in cache directory
    """
    filepath = CACHE_DIR / filename
    
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Saved to {filepath}")
    except Exception as e:
        print(f"[ERROR] Failed to save JSON: {e}")


def load_cached_json(filename: str) -> Optional[Dict]:
    """
    Load cached JSON file if it exists
    """
    filepath = CACHE_DIR / filename
    if filepath.exists():
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load cached file: {e}")
    return None


def fetch_prices(region: str = 'VIC1', hours_ahead: int = 12, hours_back: int = 0, force_refresh: bool = False) -> Optional[Dict]:
    """
    Main function to fetch electricity prices from NEMweb PUBLIC_PRICES data
    Can fetch both historical (hours_back) and future (hours_ahead) data if available
    """
    print("=" * 60)
    print("NEMweb Public Price Fetcher")
    print("=" * 60)

    # Get latest file
    result = get_latest_file_url(PUBLIC_PRICES_URL)
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache
    cache_filename = f"prices_{region.lower()}_{date_str}.json"
    if not force_refresh:
        cached = load_cached_json(cache_filename)
        if cached:
            print(f"[INFO] Using cached data from {date_str}")
            return cached

    # Download and extract
    temp_dir = download_and_extract_zip(url)
    if not temp_dir:
        return None

    try:
        # Find CSV file
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return None

        print(f"[INFO] Parsing {csv_path}...")

        # Parse CSV
        prices = parse_price_csv(csv_path, region, hours_ahead, hours_back)

        if not prices:
            print("[WARNING] No price data extracted")
            return None

        # Prepare output
        # Determine current timezone name (AEST or AEDT)
        now = datetime.now(AEST)
        tz_name = now.tzname()

        output = {
            'region': region,
            'data_date': date_str,
            'timezone': tz_name,
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_ahead': hours_ahead,
            'hours_back': hours_back,
            'prices': prices
        }

        # Save to cache
        save_to_json(output, cache_filename)

        return output

    finally:
        # Cleanup temp directory
        temp_dir.cleanup()


def fetch_p5min_prices(region: str = 'VIC1', hours_ahead: int = 1, force_refresh: bool = False) -> Optional[Dict]:
    """
    Fetch latest 5-minute predispatch prices from P5_Reports
    These are short-term forecasts (typically next hour)
    """
    print("=" * 60)
    print("NEMweb 5-Minute Predispatch Price Fetcher (P5MIN)")
    print("=" * 60)

    # Get latest file (uses timestamp pattern)
    result = get_latest_file_url(P5_REPORTS_URL, pattern=r'PUBLIC_P5MIN_(\d{12})_')
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache
    cache_filename = f"p5min_{region.lower()}_{date_str}.json"
    if not force_refresh:
        cached = load_cached_json(cache_filename)
        if cached:
            print(f"[INFO] Using cached data from {date_str}")
            return cached

    # Download and extract
    temp_dir = download_and_extract_zip(url)
    if not temp_dir:
        return None

    try:
        # Find CSV file
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return None

        print(f"[INFO] Parsing {csv_path}...")

        # Parse CSV - P5MIN uses P5MIN_REGIONSOLUTION table
        prices = parse_region_csv(csv_path, region, table_name='P5MIN', hours_ahead=hours_ahead, hours_back=0)

        if not prices:
            print("[WARNING] No price data extracted")
            return None

        # Prepare output
        now = datetime.now(AEST)
        tz_name = now.tzname()

        output = {
            'region': region,
            'data_date': date_str,
            'timezone': tz_name,
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_ahead': hours_ahead,
            'data_type': 'p5min_predispatch',
            'prices': prices
        }

        # Save to cache
        save_to_json(output, cache_filename)

        return output

    finally:
        # Cleanup temp directory
        temp_dir.cleanup()


def fetch_predispatch_prices(region: str = 'VIC1', hours_ahead: int = 24, force_refresh: bool = False) -> Optional[Dict]:
    """
    Fetch full predispatch price forecasts from Predispatch_Reports
    These are longer-term forecasts (typically 24-40 hours ahead)
    """
    print("=" * 60)
    print("NEMweb Predispatch Price Fetcher (PREDISPATCH)")
    print("=" * 60)

    # Get latest file
    result = get_latest_file_url(PREDISPATCH_REPORTS_URL, pattern=r'PUBLIC_PREDISPATCH_(\d{12})_')
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache
    cache_filename = f"predispatch_{region.lower()}_{date_str}.json"
    if not force_refresh:
        cached = load_cached_json(cache_filename)
        if cached:
            print(f"[INFO] Using cached data from {date_str}")
            return cached

    # Download and extract
    temp_dir = download_and_extract_zip(url)
    if not temp_dir:
        return None

    try:
        # Find CSV file
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return None

        print(f"[INFO] Parsing {csv_path}...")

        # Parse CSV - PREDISPATCH uses PDREGION table
        prices = parse_region_csv(csv_path, region, table_name='PDREGION', hours_ahead=hours_ahead, hours_back=0)

        if not prices:
            print("[WARNING] No price data extracted")
            return None

        # Prepare output
        now = datetime.now(AEST)
        tz_name = now.tzname()

        output = {
            'region': region,
            'data_date': date_str,
            'timezone': tz_name,
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_ahead': hours_ahead,
            'data_type': 'predispatch_forecast',
            'prices': prices
        }

        # Save to cache
        save_to_json(output, cache_filename)

        return output

    finally:
        # Cleanup temp directory
        temp_dir.cleanup()


def fetch_dispatch_prices(region: str = 'VIC1', hours_back: int = 24, force_refresh: bool = False) -> Optional[Dict]:
    """
    Fetch historical dispatch prices from Dispatch_Reports
    These are actual historical settlement prices
    """
    print("=" * 60)
    print("NEMweb Dispatch Price Fetcher (DISPATCH - Historical)")
    print("=" * 60)

    # Get latest file
    result = get_latest_file_url(DISPATCH_REPORTS_URL, pattern=r'PUBLIC_DISPATCH_(\d{12})_')
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache
    cache_filename = f"dispatch_{region.lower()}_{date_str}.json"
    if not force_refresh:
        cached = load_cached_json(cache_filename)
        if cached:
            print(f"[INFO] Using cached data from {date_str}")
            return cached

    # Download and extract
    temp_dir = download_and_extract_zip(url)
    if not temp_dir:
        return None

    try:
        # Find CSV file
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return None

        print(f"[INFO] Parsing {csv_path}...")

        # Parse CSV - DISPATCH uses DREGION table
        prices = parse_region_csv(csv_path, region, table_name='DREGION', hours_ahead=0, hours_back=hours_back)

        if not prices:
            print("[WARNING] No price data extracted")
            return None

        # Prepare output
        now = datetime.now(AEST)
        tz_name = now.tzname()

        output = {
            'region': region,
            'data_date': date_str,
            'timezone': tz_name,
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_back': hours_back,
            'data_type': 'dispatch_historical',
            'prices': prices
        }

        # Save to cache
        save_to_json(output, cache_filename)

        return output

    finally:
        # Cleanup temp directory
        temp_dir.cleanup()


def main():
    """
    Main entry point - demonstrates fetching from all three data sources
    """
    import sys

    # Check for force refresh flag
    force_refresh = '--refresh' in sys.argv or '-r' in sys.argv

    print("\n" + "="*60)
    print("NEMweb Price Fetcher - All Data Sources")
    print("="*60 + "\n")

    # Fetch from all three sources
    results = {}

    # 1. Historical dispatch prices (last 3 hours)
    print("\n[1/3] Fetching historical dispatch prices...")
    dispatch = fetch_dispatch_prices(region='VIC1', hours_back=3, force_refresh=force_refresh)
    if dispatch:
        results['dispatch'] = dispatch
        print(f"[OK] Dispatch: {len(dispatch['prices'])} historical price points")
    else:
        print("[ERROR] Dispatch: Failed to fetch")

    # 2. Short-term predispatch (next 30 minutes)
    print("\n[2/3] Fetching 5-minute predispatch...")
    # P5MIN data is only for the next ~30 minutes, so we need a shorter time window
    # Also set hours_ahead=0 and hours_back=0 to get all available data points
    p5min = fetch_p5min_prices(region='VIC1', hours_ahead=0, force_refresh=force_refresh)
    if p5min:
        results['p5min'] = p5min
        print(f"[OK] P5MIN: {len(p5min['prices'])} forecast price points")
    else:
        print("[ERROR] P5MIN: Failed to fetch")

    # 3. Full predispatch forecast (next 12 hours)
    print("\n[3/3] Fetching full predispatch forecast...")
    predispatch = fetch_predispatch_prices(region='VIC1', hours_ahead=12, force_refresh=force_refresh)
    if predispatch:
        results['predispatch'] = predispatch
        print(f"[OK] Predispatch: {len(predispatch['prices'])} forecast price points")
    else:
        print("[ERROR] Predispatch: Failed to fetch")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if results:
        for name, data in results.items():
            print(f"\n{name.upper()}:")
            print(f"  Region: {data['region']}")
            print(f"  Timezone: {data['timezone']}")
            print(f"  Source: {data['source_file']}")
            if data['prices']:
                print(f"  Price points: {len(data['prices'])}")
                print(f"  First: {data['prices'][0]}")
                print(f"  Last: {data['prices'][-1]}")

        print(f"\n[SUCCESS] Fetched data from {len(results)} source(s)")
    else:
        print("\n[ERROR] Failed to fetch from all sources")
        sys.exit(1)


if __name__ == '__main__':
    main()

