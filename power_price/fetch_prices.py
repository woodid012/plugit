"""
NEMweb Power Price Data Fetcher
Fetches and caches electricity price data from NEMweb
"""

import os
import re
import json
import zipfile
import tempfile
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import pytz

# NEMweb URLs
P5_REPORTS_URL = "https://nemweb.com.au/Reports/Current/P5_Reports/"
PREDISPATCH_REPORTS_URL = "https://nemweb.com.au/Reports/Current/Predispatch_Reports/"
DISPATCH_REPORTS_URL = "https://nemweb.com.au/Reports/Current/Dispatch_Reports/"

# Timezones
AEST_FIXED = pytz.FixedOffset(600)  # UTC+10:00 (AEST - no DST)
AEST = pytz.timezone('Australia/Sydney')  # For current time (handles DST)

# Cache
CACHE_DIR = Path(__file__).parent
UNIFIED_CACHE_FILE = CACHE_DIR / "nem_price_cache.json"

# User-Agent rotation for cache bypass
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    None
]


def get_latest_file_url(base_url: str, pattern: str, max_age_hours: int = 6,
                        user_agent: Optional[str] = None, cache_bust: bool = False) -> Optional[Tuple[str, str]]:
    """Find most recent file from NEMweb directory listing. Returns (url, timestamp) or None."""
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
        if user_agent:
            headers['User-Agent'] = user_agent
        
        url = base_url
        if cache_bust:
            separator = '&' if '?' in base_url else '?'
            url = f"{base_url}{separator}_t={int(time.time() * 1000)}"

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        files = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(pattern, href)
            if match:
                timestamp_str = match.group(1)
                if href.startswith('http'):
                    file_url = href
                elif href.startswith('/'):
                    parsed = urlparse(base_url)
                    file_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                else:
                    file_url = base_url.rstrip('/') + '/' + href
                files.append((timestamp_str, file_url))

        if not files:
            return None

        files.sort(reverse=True)
        latest_timestamp, latest_url = files[0]
        print(f"[INFO] Found latest file: {latest_timestamp}")

        if is_data_stale(latest_timestamp, max_age_hours):
            print(f"[WARNING] Latest file is {max_age_hours}+ hours old")

        return (latest_url, latest_timestamp)
    except Exception as e:
        print(f"[ERROR] Failed to fetch directory listing: {e}")
        return None


def smart_fetch_with_retry(base_url: str, pattern: str, current_cached_timestamp: Optional[str] = None,
                           max_age_hours: int = 6, max_attempts: int = 3) -> Optional[Tuple[str, str]]:
    """Retry with different User-Agents to bypass NEMweb caching."""
    best_result = None
    best_timestamp = current_cached_timestamp

    for i, user_agent in enumerate(USER_AGENTS[:max_attempts]):
        try:
            result = get_latest_file_url(base_url, pattern, max_age_hours, user_agent, cache_bust=(i % 2 == 1))
            if result:
                url, timestamp = result
                if not best_timestamp or timestamp > best_timestamp:
                    best_result = result
                    best_timestamp = timestamp
                    break
            if i < max_attempts - 1:
                time.sleep(0.5)
        except Exception as e:
            print(f"[WARNING] Attempt {i+1} failed: {e}")

    return best_result


def download_and_extract_zip(url: str, user_agent: Optional[str] = None) -> Optional[tempfile.TemporaryDirectory]:
    """Download and extract ZIP file to temporary directory."""
    try:
        headers = {'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
        if user_agent:
            headers['User-Agent'] = user_agent

        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        temp_dir = tempfile.TemporaryDirectory()
        zip_path = os.path.join(temp_dir.name, 'data.zip')
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir.name)
        
        return temp_dir
    except Exception as e:
        print(f"[ERROR] Failed to download/extract ZIP: {e}")
        return None


def find_csv_file(directory: str) -> Optional[str]:
    """Find first CSV file in directory."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.upper().endswith('.CSV'):
                return os.path.join(root, file)
    return None


def parse_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """Extract timestamp from filename like PUBLIC_DISPATCH_202511191705."""
    match = re.search(r'(\d{12})', filename)
    if match:
        try:
            ts = match.group(1)
            dt = datetime(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]), int(ts[8:10]), int(ts[10:12]))
            return AEST_FIXED.localize(dt)
        except (ValueError, IndexError):
            return None
    return None


def parse_region_csv(csv_path: str, region: str, table_name: str, hours_ahead: int = 12, 
                     hours_back: int = 0, expected_settlement_date: Optional[datetime] = None,
                     source_filename: Optional[str] = None) -> List[Dict]:
    """Parse NEMweb CSV and extract price data for specified region."""
    prices = []
    
    if expected_settlement_date is None and source_filename:
        expected_settlement_date = parse_timestamp_from_filename(source_filename)

    try:
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            now_local = datetime.now(AEST)
            cutoff_future = now_local + timedelta(hours=hours_ahead)
            cutoff_past = now_local - timedelta(hours=hours_back)

            column_headers = None
            regionid_idx = None
            datetime_idx = None
            rrp_idx = None

            for line in f:
                parts = line.strip().split(',')
                if not parts:
                    continue

                row_type = parts[0]

                # Header row
                if row_type == 'I' and len(parts) > 2 and parts[1].upper() in [table_name.upper(), table_name.split('_')[0].upper()]:
                    column_headers = [col.strip() for col in parts[4:]]
                    try:
                        regionid_idx = column_headers.index('REGIONID') if 'REGIONID' in column_headers else None
                        for col_name in ['SETTLEMENTDATE', 'PERIODID', 'INTERVAL_DATETIME']:
                            if col_name in column_headers:
                                datetime_idx = column_headers.index(col_name)
                                break
                        rrp_idx = column_headers.index('RRP') if 'RRP' in column_headers else None
                        if not all([regionid_idx, datetime_idx, rrp_idx]):
                            continue
                    except ValueError:
                        continue

                # Data row
                elif row_type == 'D' and column_headers and regionid_idx is not None:
                    table_prefix = parts[1].upper()
                    if table_prefix not in [table_name.upper(), table_name.split('_')[0].upper()]:
                        continue

                    values = parts[4:]
                    if len(values) <= max(regionid_idx, datetime_idx, rrp_idx):
                        continue

                    try:
                        row_region = values[regionid_idx].strip()
                        if row_region != region:
                            continue

                        dt_str = values[datetime_idx].strip().strip('"')
                        price_str = values[rrp_idx].strip()

                        # Parse datetime
                        dt = None
                        for fmt in ['%Y/%m/%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%d/%m/%Y %H:%M']:
                            try:
                                dt = datetime.strptime(dt_str, fmt)
                                break
                            except ValueError:
                                continue

                        if dt is None:
                            continue

                        dt_local = AEST_FIXED.localize(dt)

                        # Validate settlement date for dispatch reports
                        if expected_settlement_date and table_name.upper() == 'DREGION':
                            time_diff = abs((dt_local - expected_settlement_date).total_seconds())
                            if time_diff > 60:
                                continue
                            elif time_diff > 0:
                                dt_local = expected_settlement_date

                        # Filter by time range
                        if hours_back > 0:
                            future_tolerance = timedelta(minutes=15)
                            if dt_local < cutoff_past or dt_local > (now_local + future_tolerance):
                                continue
                        elif hours_ahead > 0:
                            if dt_local <= now_local or dt_local > cutoff_future:
                                continue

                        price = float(price_str)
                        prices.append({
                            'timestamp': dt_local.isoformat(),
                            'price': round(price, 2)
                        })
                    except (ValueError, IndexError):
                        continue

            prices.sort(key=lambda x: x['timestamp'])
            print(f"[OK] Extracted {len(prices)} price points for {region}")
            return prices

    except Exception as e:
        print(f"[ERROR] Failed to parse CSV: {e}")
        return []


# Cache management
def load_unified_cache() -> Dict:
    """Load unified cache file."""
    if UNIFIED_CACHE_FILE.exists():
        try:
            with open(UNIFIED_CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load cache: {e}")

    return {
        "dispatch": {},
        "p5min": {},
        "predispatch": {},
        "metadata": {"created_at": datetime.now(AEST).isoformat()}
    }


def save_unified_cache(cache: Dict):
    """Save unified cache file."""
    try:
        cache["metadata"]["last_updated"] = datetime.now(AEST).isoformat()
        with open(UNIFIED_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save cache: {e}")


def get_from_cache(data_type: str, timestamp_key: str) -> Optional[Dict]:
    """Get data from unified cache."""
    cache = load_unified_cache()
    if data_type in cache and timestamp_key in cache[data_type]:
        print(f"[INFO] Using cached {data_type} data from {timestamp_key}")
        return cache[data_type][timestamp_key]
    return None


def is_data_stale(timestamp_key: str, max_age_hours: int = 6) -> bool:
    """Check if data timestamp is stale."""
    try:
        year, month, day = int(timestamp_key[0:4]), int(timestamp_key[4:6]), int(timestamp_key[6:8])
        hour, minute = int(timestamp_key[8:10]), int(timestamp_key[10:12])
        data_time = AEST.localize(datetime(year, month, day, hour, minute))
        age_hours = (datetime.now(AEST) - data_time).total_seconds() / 3600
        return age_hours > max_age_hours
    except Exception:
        return False


def save_to_cache(data_type: str, timestamp_key: str, data: Dict):
    """Save data to unified cache with validation."""
    cache = load_unified_cache()
    if data_type not in cache:
        cache[data_type] = {}

    if cache[data_type]:
        latest_cached_key = max(cache[data_type].keys())
        if timestamp_key < latest_cached_key:
            print(f"[WARNING] Fetched {data_type} data ({timestamp_key}) is OLDER than cached ({latest_cached_key})")
            return

    if is_data_stale(timestamp_key, max_age_hours=6):
        print(f"[WARNING] {data_type} data appears stale")

    cache[data_type][timestamp_key] = data

    # Keep only recent entries
    max_entries = 24 if data_type == 'dispatch' else 10
    if len(cache[data_type]) > max_entries:
        sorted_keys = sorted(cache[data_type].keys(), reverse=True)
        cache[data_type] = {k: cache[data_type][k] for k in sorted_keys[:max_entries]}

    save_unified_cache(cache)


def save_to_json(data: Dict, filename: str):
    """Legacy compatibility - save to unified cache."""
    parts = filename.replace('.json', '').split('_')
    data_type = parts[0]
    timestamp_key = parts[-1]
    save_to_cache(data_type, timestamp_key, data)


def load_cached_json(filename: str) -> Optional[Dict]:
    """Legacy compatibility - load from unified cache."""
    parts = filename.replace('.json', '').split('_')
    data_type = parts[0]
    timestamp_key = parts[-1]
    return get_from_cache(data_type, timestamp_key)


# Main fetch functions
def fetch_p5min_prices(region: str = 'VIC1', hours_ahead: int = 1, force_refresh: bool = False) -> Optional[Dict]:
    """Fetch 5-minute predispatch prices."""
    print("=" * 60)
    print("NEMweb 5-Minute Predispatch Price Fetcher")
    print("=" * 60)

    cache = load_unified_cache()
    current_timestamp = max(cache['p5min'].keys()) if cache.get('p5min') else None

    result = smart_fetch_with_retry(
        P5_REPORTS_URL,
        pattern=r'PUBLIC_P5MIN_(\d{12})_',
        current_cached_timestamp=current_timestamp if force_refresh else None,
        max_attempts=3
    )
    if not result:
        return None

    url, date_str = result

    if not force_refresh and date_str == current_timestamp:
        cached_data = cache['p5min'].get(date_str)
        if cached_data and cached_data.get('region') == region:
            print(f"[INFO] Using cached data from {date_str}")
            return cached_data

    user_agent = random.choice([ua for ua in USER_AGENTS if ua is not None])
    temp_dir = download_and_extract_zip(url, user_agent=user_agent)
    if not temp_dir:
        return None

    try:
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found")
            return None

        prices = parse_region_csv(csv_path, region, table_name='P5MIN', hours_ahead=hours_ahead, hours_back=0)
        if not prices:
            return None

        now = datetime.now(AEST)
        output = {
            'region': region,
            'data_date': date_str,
            'timezone': now.tzname(),
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_ahead': hours_ahead,
            'data_type': 'p5min_predispatch',
            'prices': prices
        }

        save_to_json(output, f"p5min_{region.lower()}_{date_str}.json")
        return output
    finally:
        temp_dir.cleanup()


def fetch_predispatch_prices(region: str = 'VIC1', hours_ahead: int = 24, force_refresh: bool = False) -> Optional[Dict]:
    """Fetch full predispatch price forecasts."""
    print("=" * 60)
    print("NEMweb Predispatch Price Fetcher")
    print("=" * 60)

    cache = load_unified_cache()
    current_timestamp = max(cache['predispatch'].keys()) if cache.get('predispatch') else None

    result = smart_fetch_with_retry(
        PREDISPATCH_REPORTS_URL,
        pattern=r'PUBLIC_PREDISPATCH_(\d{12})_',
        current_cached_timestamp=current_timestamp if force_refresh else None,
        max_attempts=3
    )
    if not result:
        return None

    url, date_str = result

    if not force_refresh and date_str == current_timestamp:
        cached_data = cache['predispatch'].get(date_str)
        if cached_data and cached_data.get('region') == region:
            print(f"[INFO] Using cached data from {date_str}")
            return cached_data

    user_agent = random.choice([ua for ua in USER_AGENTS if ua is not None])
    temp_dir = download_and_extract_zip(url, user_agent=user_agent)
    if not temp_dir:
        return None

    try:
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found")
            return None

        prices = parse_region_csv(csv_path, region, table_name='PDREGION', hours_ahead=hours_ahead, hours_back=0)
        if not prices:
            return None

        now = datetime.now(AEST)
        output = {
            'region': region,
            'data_date': date_str,
            'timezone': now.tzname(),
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_ahead': hours_ahead,
            'data_type': 'predispatch_forecast',
            'prices': prices
        }

        save_to_json(output, f"predispatch_{region.lower()}_{date_str}.json")
        return output
    finally:
        temp_dir.cleanup()


def fetch_dispatch_prices(region: str = 'VIC1', hours_back: int = 24, force_refresh: bool = False) -> Optional[Dict]:
    """Fetch historical dispatch prices."""
    print("=" * 60)
    print("NEMweb Dispatch Price Fetcher (Historical)")
    print("=" * 60)

    cache = load_unified_cache()
    current_timestamp = max(cache['dispatch'].keys()) if cache.get('dispatch') else None

    result = smart_fetch_with_retry(
        DISPATCH_REPORTS_URL,
        pattern=r'PUBLIC_DISPATCH_(\d{12})_',
        current_cached_timestamp=current_timestamp if force_refresh else None,
        max_attempts=3
    )
    if not result:
        return None

    url, date_str = result

    if not force_refresh and date_str == current_timestamp:
        cached_data = cache['dispatch'].get(date_str)
        if cached_data and cached_data.get('region') == region:
            print(f"[INFO] Using cached data from {date_str}")
            return cached_data

    user_agent = random.choice([ua for ua in USER_AGENTS if ua is not None])
    temp_dir = download_and_extract_zip(url, user_agent=user_agent)
    if not temp_dir:
        return None

    try:
        csv_path = find_csv_file(temp_dir.name)
        if not csv_path:
            print("[ERROR] No CSV file found")
            return None

        expected_settlement_date = parse_timestamp_from_filename(os.path.basename(url))
        prices = parse_region_csv(
            csv_path, region, table_name='DREGION', hours_ahead=0, hours_back=hours_back,
            expected_settlement_date=expected_settlement_date, source_filename=os.path.basename(url)
        )
        if not prices:
            return None

        now = datetime.now(AEST)
        output = {
            'region': region,
            'data_date': date_str,
            'timezone': now.tzname(),
            'source_file': os.path.basename(url),
            'fetched_at': now.isoformat(),
            'hours_back': hours_back,
            'data_type': 'dispatch_historical',
            'prices': prices
        }

        save_to_json(output, f"dispatch_{region.lower()}_{date_str}.json")
        return output
    finally:
        temp_dir.cleanup()


def get_latest_cached_data() -> Dict:
    """Get most recent cached data from all sources."""
    cache = load_unified_cache()
    result = {
        'metadata': {
            'fetched_at': datetime.now(AEST).isoformat(),
            'cache_updated': cache.get('metadata', {}).get('last_updated'),
        },
        'data': {}
    }

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache and cache[data_type]:
            latest_timestamp = max(cache[data_type].keys())
            result['data'][data_type] = cache[data_type][latest_timestamp]

    return result


def export_for_api() -> Dict:
    """Export cached data for API/database insertion."""
    cache = load_unified_cache()
    all_prices = []

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache:
            for timestamp_key, data in cache[data_type].items():
                region = data.get('region')
                if not region:
                    continue
                for price_point in data.get('prices', []):
                    all_prices.append({
                        'timestamp': price_point['timestamp'],
                        'price': price_point['price'],
                        'data_type': data_type,
                        'source_file': data.get('source_file', ''),
                        'region': region,
                        'fetched_at': data.get('fetched_at', '')
                    })

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
    """Main entry point - fetch from all three data sources."""
    import sys
    force_refresh = '--refresh' in sys.argv or '-r' in sys.argv

    print("\n" + "="*60)
    print("NEMweb Price Fetcher - All Data Sources")
    print("="*60 + "\n")

    results = {}

    print("\n[1/3] Fetching historical dispatch prices...")
    dispatch = fetch_dispatch_prices(region='VIC1', hours_back=3, force_refresh=force_refresh)
    if dispatch:
        results['dispatch'] = dispatch
        print(f"[OK] Dispatch: {len(dispatch['prices'])} price points")

    print("\n[2/3] Fetching 5-minute predispatch...")
    p5min = fetch_p5min_prices(region='VIC1', hours_ahead=0, force_refresh=force_refresh)
    if p5min:
        results['p5min'] = p5min
        print(f"[OK] P5MIN: {len(p5min['prices'])} price points")

    print("\n[3/3] Fetching full predispatch forecast...")
    predispatch = fetch_predispatch_prices(region='VIC1', hours_ahead=12, force_refresh=force_refresh)
    if predispatch:
        results['predispatch'] = predispatch
        print(f"[OK] Predispatch: {len(predispatch['prices'])} price points")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if results:
        for name, data in results.items():
            print(f"\n{name.upper()}: {len(data['prices'])} points")
    else:
        print("\n[ERROR] Failed to fetch from all sources")
        sys.exit(1)


if __name__ == '__main__':
    main()
