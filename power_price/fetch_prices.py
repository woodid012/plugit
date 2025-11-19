"""
NEMweb Power Price Data Fetcher
Downloads and caches electricity price data from NEMweb for VIC1 region

IMPORTANT: NEMweb Caching Issues
--------------------------------
NEMweb has known caching issues on their servers. Sometimes when requesting data,
you may receive stale/cached responses even though newer data is available.

WORKAROUND: Changing the User-Agent header or using different browser sessions
sometimes helps bypass their cache and retrieve fresher data. If implementing
improvements to this fetcher, consider:
  - Rotating User-Agent strings
  - Adding cache-busting query parameters
  - Setting appropriate cache-control headers (Cache-Control: no-cache)
  - Using different request sessions

This is a server-side issue on NEMweb's end, not a bug in this code.
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
# NEMweb market timestamps are ALWAYS in AEST (UTC+10), regardless of DST
# We need a fixed AEST timezone that doesn't change with daylight saving
AEST_FIXED = pytz.FixedOffset(600)  # UTC+10:00 (AEST - Australian Eastern Standard Time)
AEST = pytz.timezone('Australia/Sydney')  # For current time calculations (handles AEST/AEDT automatically)
UTC = pytz.UTC

# Cache directory (same as script directory)
CACHE_DIR = Path(__file__).parent

# User-Agent rotation to bypass NEMweb caching
# Different browsers/platforms to simulate fresh requests
USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    # Firefox on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    # Edge on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    # Safari on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    # Chrome on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    # Generic Python requests (default)
    None  # Uses default requests User-Agent
]

import random
import time


def get_latest_file_url(base_url: str, pattern: str = r'PUBLIC_PRICES_(\d{8})\d{4}', max_age_hours: int = 6,
                        user_agent: Optional[str] = None, cache_bust: bool = False) -> Optional[tuple]:
    """
    Parse HTML directory listing to find the most recent file by date (YYYYMMDD)
    Returns tuple of (url, date_string) or None

    Args:
        base_url: NEMweb directory URL
        pattern: regex pattern to match files
        max_age_hours: warn if latest file is older than this many hours
        user_agent: Custom User-Agent header (None = default)
        cache_bust: Add timestamp query parameter to bypass cache
    """
    try:
        # Prepare headers
        headers = {}
        if user_agent:
            headers['User-Agent'] = user_agent

        # Add cache-control headers to request fresh data
        headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        headers['Pragma'] = 'no-cache'

        # Add cache-busting query parameter
        url = base_url
        if cache_bust:
            separator = '&' if '?' in base_url else '?'
            url = f"{base_url}{separator}_t={int(time.time() * 1000)}"

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Collect all matching files with their timestamps
        files = []

        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(pattern, href)
            if match:
                timestamp_str = match.group(1)  # Full timestamp (YYYYMMDDTTTT)

                # Build URL
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    from urllib.parse import urlparse
                    parsed = urlparse(base_url)
                    url = f"{parsed.scheme}://{parsed.netloc}{href}"
                else:
                    url = base_url.rstrip('/') + '/' + href

                files.append((timestamp_str, url))

        if not files:
            print("[WARNING] No matching files found")
            return None

        # Sort by timestamp (most recent first)
        files.sort(reverse=True)

        # Get the most recent file
        latest_timestamp, latest_url = files[0]

        print(f"[INFO] Found latest file: {latest_timestamp}")

        # Check if the latest file is stale
        if is_data_stale(latest_timestamp, max_age_hours):
            print(f"[WARNING] NEMweb's latest file is {max_age_hours}+ hours old!")
            print(f"[INFO] This may indicate NEMweb caching issues or delayed updates")

            # Show when we expect fresh data
            try:
                year = int(latest_timestamp[0:4])
                month = int(latest_timestamp[4:6])
                day = int(latest_timestamp[6:8])
                hour = int(latest_timestamp[8:10])
                minute = int(latest_timestamp[10:12])
                data_time = AEST.localize(datetime(year, month, day, hour, minute))
                now = datetime.now(AEST)
                age = (now - data_time).total_seconds() / 3600
                print(f"[INFO] Data age: {age:.1f} hours (from {data_time.strftime('%Y-%m-%d %H:%M')})")
            except:
                pass

        return (latest_url, latest_timestamp)

    except Exception as e:
        print(f"[ERROR] Failed to fetch directory listing: {e}")
        return None


def download_and_extract_zip(url: str, user_agent: Optional[str] = None) -> Optional[tempfile.TemporaryDirectory]:
    """
    Download ZIP file and extract to temporary directory
    Returns TemporaryDirectory object or None
    """
    try:
        print(f"[INFO] Downloading {url}...")

        # Prepare headers
        headers = {}
        if user_agent:
            headers['User-Agent'] = user_agent
        headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        headers['Pragma'] = 'no-cache'

        response = requests.get(url, headers=headers, timeout=60)
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


def smart_fetch_with_retry(base_url: str, pattern: str, current_cached_timestamp: Optional[str] = None,
                           max_age_hours: int = 6, max_attempts: int = 5) -> Optional[tuple]:
    """
    Smart retry mechanism to bypass NEMweb caching issues.
    Tries multiple User-Agents and cache-busting strategies to get fresh data.

    Args:
        base_url: NEMweb directory URL
        pattern: regex pattern to match files
        current_cached_timestamp: The timestamp of data we already have (to compare)
        max_age_hours: warn if latest file is older than this many hours
        max_attempts: maximum number of attempts with different strategies

    Returns:
        tuple of (url, timestamp) if newer data found, None otherwise
    """
    print(f"[INFO] Attempting smart fetch with retry (up to {max_attempts} attempts)...")

    best_result = None
    best_timestamp = current_cached_timestamp

    strategies = []
    # Create combinations of User-Agents and cache-busting
    for i, ua in enumerate(USER_AGENTS[:max_attempts]):
        cache_bust = (i % 2 == 1)  # Alternate cache-busting on/off
        strategies.append((ua, cache_bust))

    for attempt, (user_agent, cache_bust) in enumerate(strategies, 1):
        try:
            ua_name = "Default" if user_agent is None else user_agent.split('(')[1].split(')')[0] if '(' in user_agent else "Custom"
            strategy_desc = f"User-Agent: {ua_name}, Cache-bust: {cache_bust}"
            print(f"[RETRY {attempt}/{len(strategies)}] Trying: {strategy_desc}")

            result = get_latest_file_url(base_url, pattern=pattern, max_age_hours=max_age_hours,
                                        user_agent=user_agent, cache_bust=cache_bust)

            if result:
                url, timestamp = result

                # Check if this is newer than what we have
                if not best_timestamp or timestamp > best_timestamp:
                    print(f"[SUCCESS] Found newer data! Timestamp: {timestamp} (previous: {best_timestamp or 'none'})")
                    best_result = result
                    best_timestamp = timestamp
                    # If we found newer data, we can stop trying
                    break
                else:
                    print(f"[INFO] Same timestamp as before: {timestamp}")

            # Small delay between attempts to avoid hammering the server
            if attempt < len(strategies):
                time.sleep(0.5)

        except Exception as e:
            print(f"[WARNING] Attempt {attempt} failed: {e}")
            continue

    if best_result and best_result[1] != current_cached_timestamp:
        print(f"[SUCCESS] Smart fetch succeeded! New timestamp: {best_result[1]}")
        return best_result
    elif best_result:
        print(f"[INFO] No newer data available. Latest: {best_result[1]}")
        return best_result
    else:
        print(f"[ERROR] All retry attempts failed")
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
                        # NEMweb uses DD/MM/YYYY format, but also supports YYYY/MM/DD
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
                            continue

                        # Localize to AEST (UTC+10) - NEMweb market timestamps are always in AEST
                        # regardless of whether we're currently in daylight saving time
                        dt_local = AEST_FIXED.localize(dt)

                        # Filter by time range
                        # Include data within the specified time window (past or future)
                        if hours_back > 0:
                            # Historical mode: include data from past, and allow up to 15 minutes in future
                            # (dispatch data can be published slightly ahead of current time)
                            future_tolerance = timedelta(minutes=15)
                            if dt_local < cutoff_past or dt_local > (now_local + future_tolerance):
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


def parse_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """
    Parse timestamp from NEMweb filename and convert to datetime
    Example: PUBLIC_DISPATCH_202511191705_20251119170021_LEGACY.zip -> 2025-11-19 17:05:00
    
    Returns datetime object in AEST timezone, or None if parsing fails
    """
    import re
    # Pattern matches YYYYMMDDHHMM (12 digits) - first occurrence is the settlement date
    match = re.search(r'(\d{12})', filename)
    if match:
        timestamp_str = match.group(1)
        try:
            # Parse YYYYMMDDHHMM format
            year = int(timestamp_str[0:4])
            month = int(timestamp_str[4:6])
            day = int(timestamp_str[6:8])
            hour = int(timestamp_str[8:10])
            minute = int(timestamp_str[10:12])
            # Create datetime and localize to AEST
            dt = datetime(year, month, day, hour, minute, 0)
            return AEST_FIXED.localize(dt)
        except (ValueError, IndexError) as e:
            print(f"[WARNING] Could not parse timestamp from filename {filename}: {e}")
            return None
    return None


def parse_region_csv(csv_path: str, region: str = 'VIC1', table_name: str = 'DREGION',
                     hours_ahead: int = 12, hours_back: int = 0,
                     expected_settlement_date: Optional[datetime] = None,
                     source_filename: Optional[str] = None) -> List[Dict]:
    """
    Generic parser for regional price data from NEMweb CSV files
    Handles DREGION (dispatch), PDREGION (predispatch), and P5MIN_REGIONSOLUTION (5-min predispatch)

    Args:
        csv_path: Path to CSV file
        region: Region code (e.g., 'VIC1')
        table_name: Table name to parse (e.g., 'DREGION')
        hours_ahead: Hours ahead to include (for forecast data)
        hours_back: Hours back to include (for historical data)
        expected_settlement_date: Expected settlement date from filename (for validation)
        source_filename: Source filename for extracting expected settlement date if not provided

    Returns list of {timestamp, price} dictionaries
    """
    prices = []
    
    # If expected_settlement_date not provided but source_filename is, extract it
    if expected_settlement_date is None and source_filename:
        expected_settlement_date = parse_timestamp_from_filename(source_filename)
        if expected_settlement_date:
            print(f"[INFO] Expected settlement date from filename: {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')}")

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
                        
                        # Debug output for first few VIC1 rows
                        if row_region == 'VIC1' and len(prices) < 3:
                            print(f"[DEBUG] Found VIC1 row: timestamp={dt_str}, price={price_str}")

                        # Parse datetime
                        # NEMweb uses DD/MM/YYYY format, but also supports YYYY/MM/DD
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
                            continue

                        # Localize to AEST (UTC+10) - NEMweb market timestamps are always in AEST
                        # regardless of whether we're currently in daylight saving time
                        dt_local = AEST_FIXED.localize(dt)
                        
                        # Validate settlement date matches filename timestamp (for dispatch reports)
                        # The SETTLEMENTDATE in the CSV row must equal the settlement date in the filename
                        if expected_settlement_date and table_name.upper() == 'DREGION':
                            # Compare settlement date to expected date from filename
                            # Allow exact match or very small difference (within 1 minute for rounding)
                            time_diff_seconds = abs((dt_local - expected_settlement_date).total_seconds())
                            if time_diff_seconds > 60:  # More than 1 minute difference
                                print(f"[WARNING] Settlement date mismatch: CSV row has {dt_local.strftime('%d/%m/%Y %H:%M:%S')}, "
                                      f"filename expects {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')} "
                                      f"(difference: {time_diff_seconds:.0f} seconds) - SKIPPING ROW")
                                continue
                            elif time_diff_seconds > 0:
                                # Small difference (within 1 minute) - use expected date from filename for consistency
                                print(f"[INFO] Adjusting settlement date from {dt_local.strftime('%d/%m/%Y %H:%M:%S')} "
                                      f"to {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')} to match filename")
                                dt_local = expected_settlement_date

                        # Filter by time range
                        # Include data within the specified time window (past or future)
                        if hours_back > 0:
                            # Historical mode: include data from past, and allow up to 15 minutes in future
                            # (dispatch data can be published slightly ahead of current time)
                            future_tolerance = timedelta(minutes=15)
                            if dt_local < cutoff_past or dt_local > (now_local + future_tolerance):
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


UNIFIED_CACHE_FILE = CACHE_DIR / "nem_price_cache.json"


def load_unified_cache() -> Dict:
    """
    Load the unified cache file containing all data sources
    Returns dict with structure:
    {
        "dispatch": {"202511182020": {...}, ...},
        "p5min": {"202511182020": {...}, ...},
        "predispatch": {"202511182030": {...}, ...}
    }
    """
    if UNIFIED_CACHE_FILE.exists():
        try:
            with open(UNIFIED_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load unified cache: {e}")

    # Return empty structure
    return {
        "dispatch": {},
        "p5min": {},
        "predispatch": {},
        "metadata": {
            "created_at": datetime.now(AEST).isoformat(),
            "description": "Unified NEMweb price data cache"
        }
    }


def save_unified_cache(cache: Dict):
    """
    Save the unified cache file
    """
    try:
        cache["metadata"]["last_updated"] = datetime.now(AEST).isoformat()
        with open(UNIFIED_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
        print(f"[OK] Updated unified cache: {UNIFIED_CACHE_FILE}")
    except Exception as e:
        print(f"[ERROR] Failed to save unified cache: {e}")


def get_from_cache(data_type: str, timestamp_key: str) -> Optional[Dict]:
    """
    Get data from unified cache

    Args:
        data_type: 'dispatch', 'p5min', or 'predispatch'
        timestamp_key: timestamp string like '202511182020'
    """
    cache = load_unified_cache()
    if data_type in cache and timestamp_key in cache[data_type]:
        print(f"[INFO] Using cached {data_type} data from {timestamp_key}")
        return cache[data_type][timestamp_key]
    return None


def is_data_stale(timestamp_key: str, max_age_hours: int = 6) -> bool:
    """
    Check if data timestamp is too old (stale)

    Args:
        timestamp_key: timestamp string like '202511182020'
        max_age_hours: maximum age in hours before considering stale

    Returns:
        True if data is stale, False otherwise
    """
    try:
        # Parse timestamp: YYYYMMDDTTTT (e.g., 202511182020 = 2025-11-18 20:20)
        year = int(timestamp_key[0:4])
        month = int(timestamp_key[4:6])
        day = int(timestamp_key[6:8])
        hour = int(timestamp_key[8:10])
        minute = int(timestamp_key[10:12])

        data_time = AEST.localize(datetime(year, month, day, hour, minute))
        now = datetime.now(AEST)

        age_hours = (now - data_time).total_seconds() / 3600

        if age_hours > max_age_hours:
            print(f"[WARNING] Data is {age_hours:.1f} hours old (stale)")
            return True

        return False
    except Exception as e:
        print(f"[WARNING] Could not parse timestamp {timestamp_key}: {e}")
        return False


def save_to_cache(data_type: str, timestamp_key: str, data: Dict):
    """
    Save data to unified cache with validation
    - Won't overwrite newer data with older data
    - Warns if data appears stale

    Args:
        data_type: 'dispatch', 'p5min', or 'predispatch'
        timestamp_key: timestamp string like '202511182020'
        data: the data to cache
    """
    cache = load_unified_cache()

    if data_type not in cache:
        cache[data_type] = {}

    # Check if we already have newer data
    if cache[data_type]:
        latest_cached_key = max(cache[data_type].keys())

        if timestamp_key < latest_cached_key:
            print(f"[WARNING] Fetched {data_type} data ({timestamp_key}) is OLDER than cached data ({latest_cached_key})")
            print(f"[INFO] Skipping save to prevent overwriting newer data")
            return  # Don't save older data
        elif timestamp_key == latest_cached_key:
            print(f"[INFO] Updating existing {data_type} cache entry {timestamp_key}")

    # Check if data is stale (but still save it if it's newer than what we have)
    if is_data_stale(timestamp_key, max_age_hours=6):
        print(f"[WARNING] {data_type} data appears stale (timestamp: {timestamp_key})")

    cache[data_type][timestamp_key] = data

    # Keep only the most recent entries per data type to prevent cache bloat
    # For dispatch, keep more entries (24 = 2 hours of 5-minute intervals) to allow building 1-hour historical windows
    max_entries = 24 if data_type == 'dispatch' else 10
    if len(cache[data_type]) > max_entries:
        # Sort by timestamp key and keep the most recent entries
        sorted_keys = sorted(cache[data_type].keys(), reverse=True)
        cache[data_type] = {k: cache[data_type][k] for k in sorted_keys[:max_entries]}

    save_unified_cache(cache)


def save_to_json(data: Dict, filename: str):
    """
    Legacy function for backwards compatibility
    Redirects to unified cache
    """
    # Extract data type and timestamp from filename
    # e.g., "dispatch_vic1_202511182020.json" -> "dispatch", "202511182020"
    parts = filename.replace('.json', '').split('_')
    data_type = parts[0]
    timestamp_key = parts[-1]

    save_to_cache(data_type, timestamp_key, data)


def load_cached_json(filename: str) -> Optional[Dict]:
    """
    Legacy function for backwards compatibility
    Redirects to unified cache
    """
    parts = filename.replace('.json', '').split('_')
    data_type = parts[0]
    timestamp_key = parts[-1]

    return get_from_cache(data_type, timestamp_key)


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

    # Get current cached timestamp to compare against
    cache = load_unified_cache()
    current_timestamp = None
    if 'p5min' in cache and cache['p5min']:
        current_timestamp = max(cache['p5min'].keys())
        print(f"[INFO] Current cached timestamp: {current_timestamp}")

    # Use smart retry to bypass NEMweb caching
    result = smart_fetch_with_retry(
        P5_REPORTS_URL,
        pattern=r'PUBLIC_P5MIN_(\d{12})_',
        current_cached_timestamp=current_timestamp if force_refresh else None,
        max_attempts=5
    )
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache - skip if we already have this timestamp and not forcing refresh
    cache_filename = f"p5min_{region.lower()}_{date_str}.json"
    if not force_refresh and date_str == current_timestamp:
        # Check if cached data exists and matches the requested region
        cached_data = cache['p5min'].get(date_str)
        if cached_data and cached_data.get('region') == region:
            print(f"[INFO] Using cached data from {date_str} for {region}")
            return cached_data

    # Pick a random User-Agent for download (helps with cache bypass)
    user_agent = random.choice([ua for ua in USER_AGENTS if ua is not None])

    # Download and extract
    temp_dir = download_and_extract_zip(url, user_agent=user_agent)
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

    # Get current cached timestamp to compare against
    cache = load_unified_cache()
    current_timestamp = None
    if 'predispatch' in cache and cache['predispatch']:
        current_timestamp = max(cache['predispatch'].keys())
        print(f"[INFO] Current cached timestamp: {current_timestamp}")

    # Use smart retry to bypass NEMweb caching
    result = smart_fetch_with_retry(
        PREDISPATCH_REPORTS_URL,
        pattern=r'PUBLIC_PREDISPATCH_(\d{12})_',
        current_cached_timestamp=current_timestamp if force_refresh else None,
        max_attempts=5
    )
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache - skip if we already have this timestamp and not forcing refresh
    cache_filename = f"predispatch_{region.lower()}_{date_str}.json"
    if not force_refresh and date_str == current_timestamp:
        # Check if cached data exists and matches the requested region
        cached_data = cache['predispatch'].get(date_str)
        if cached_data and cached_data.get('region') == region:
            print(f"[INFO] Using cached data from {date_str} for {region}")
            return cached_data

    # Pick a random User-Agent for download (helps with cache bypass)
    user_agent = random.choice([ua for ua in USER_AGENTS if ua is not None])

    # Download and extract
    temp_dir = download_and_extract_zip(url, user_agent=user_agent)
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

    # Get current cached timestamp to compare against
    cache = load_unified_cache()
    current_timestamp = None
    if 'dispatch' in cache and cache['dispatch']:
        current_timestamp = max(cache['dispatch'].keys())
        print(f"[INFO] Current cached timestamp: {current_timestamp}")

    # Use smart retry to bypass NEMweb caching
    result = smart_fetch_with_retry(
        DISPATCH_REPORTS_URL,
        pattern=r'PUBLIC_DISPATCH_(\d{12})_',
        current_cached_timestamp=current_timestamp if force_refresh else None,
        max_attempts=5
    )
    if not result:
        print("[ERROR] Could not find latest file")
        return None

    url, date_str = result

    # Check cache - skip if we already have this timestamp and not forcing refresh
    cache_filename = f"dispatch_{region.lower()}_{date_str}.json"
    if not force_refresh and date_str == current_timestamp:
        # Check if cached data exists and matches the requested region
        cached_data = cache['dispatch'].get(date_str)
        if cached_data and cached_data.get('region') == region:
            print(f"[INFO] Using cached data from {date_str} for {region}")
            return cached_data

    # Pick a random User-Agent for download (helps with cache bypass)
    user_agent = random.choice([ua for ua in USER_AGENTS if ua is not None])

    # Download and extract
    temp_dir = download_and_extract_zip(url, user_agent=user_agent)
    if not temp_dir:
        return None

    try:
        # Find CSV file
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found in ZIP")
            return None

        print(f"[INFO] Parsing {csv_path}...")

        # Extract expected settlement date from filename
        expected_settlement_date = parse_timestamp_from_filename(os.path.basename(url))
        if expected_settlement_date:
            print(f"[INFO] Expected settlement date from filename: {expected_settlement_date.strftime('%d/%m/%Y %H:%M:%S')}")

        # Parse CSV - DISPATCH uses DREGION table
        # Pass expected settlement date for validation
        prices = parse_region_csv(
            csv_path, 
            region, 
            table_name='DREGION', 
            hours_ahead=0, 
            hours_back=hours_back,
            expected_settlement_date=expected_settlement_date,
            source_filename=os.path.basename(url)
        )

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


def get_latest_cached_data() -> Dict:
    """
    Get the most recent cached data from all three sources
    Returns a combined dataset ready for API/database export
    """
    cache = load_unified_cache()
    result = {
        'metadata': {
            'fetched_at': datetime.now(AEST).isoformat(),
            'cache_updated': cache.get('metadata', {}).get('last_updated', None),
        },
        'data': {}
    }

    # Get latest from each data type
    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache and cache[data_type]:
            # Get the most recent timestamp
            latest_timestamp = max(cache[data_type].keys())
            result['data'][data_type] = cache[data_type][latest_timestamp]

    return result


def export_for_api() -> Dict:
    """
    Export cached data in a format optimized for API/database insertion
    Combines all price points from all sources into a flat structure
    """
    cache = load_unified_cache()

    all_prices = []

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache:
            for timestamp_key, data in cache[data_type].items():
                # Get region from data, skip if region is missing (shouldn't happen)
                region = data.get('region')
                if not region:
                    continue  # Skip entries without region
                for price_point in data.get('prices', []):
                    all_prices.append({
                        'timestamp': price_point['timestamp'],
                        'price': price_point['price'],
                        'data_type': data_type,
                        'source_file': data.get('source_file', ''),
                        'region': region,
                        'fetched_at': data.get('fetched_at', '')
                    })

    # Sort by timestamp
    all_prices.sort(key=lambda x: x['timestamp'])

    return {
        'metadata': {
            'total_records': len(all_prices),
            'exported_at': datetime.now(AEST).isoformat(),
            'cache_file': str(UNIFIED_CACHE_FILE)
        },
        'prices': all_prices
    }


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

