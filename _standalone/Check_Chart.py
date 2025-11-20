"""
Check Chart - Standalone script to visualize historical and forecast prices from MongoDB
Shows data for 4 states: VIC1, NSW1, QLD1, SA1

Requirements:
    pip install matplotlib pymongo pytz

Usage:
    python _standalone/Check_Chart.py

Output:
    Saves chart to _standalone/Check_Chart.png
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pytz
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# MongoDB connection
try:
    from mongodb.connection import connect_mongo, DB_NAME, PRICE_COLLECTION_NAME
except ImportError:
    # Fallback if mongodb module not available
    try:
        from IoS_logins import MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_NAME
        DB_NAME = MONGO_DB_NAME
        PRICE_COLLECTION_NAME = MONGO_COLLECTION_NAME
        from pymongo import MongoClient
        from pymongo.server_api import ServerApi
        def connect_mongo():
            try:
                client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
                client.admin.command('ping')
                return client
            except Exception as e:
                print(f"[ERROR] MongoDB connection failed: {e}")
                return None
    except ImportError:
        MONGO_URI = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
        DB_NAME = "nem_prices"
        PRICE_COLLECTION_NAME = "price_data"
        from pymongo import MongoClient
        from pymongo.server_api import ServerApi
        def connect_mongo():
            try:
                client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
                client.admin.command('ping')
                return client
            except Exception as e:
                print(f"[ERROR] MongoDB connection failed: {e}")
                return None

# Timezone
AEST = pytz.timezone('Australia/Sydney')

# Regions to plot (4 main states)
REGIONS = ['VIC1', 'NSW1', 'QLD1', 'SA1']
REGION_NAMES = {
    'VIC1': 'Victoria',
    'NSW1': 'New South Wales',
    'QLD1': 'Queensland',
    'SA1': 'South Australia'
}


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse ISO timestamp string to datetime object"""
    try:
        if isinstance(timestamp_str, str):
            # Handle ISO format with timezone
            if '+' in timestamp_str or timestamp_str.endswith('Z'):
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1] + '+00:00'
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                # Convert to AEST
                if dt.tzinfo is None:
                    dt = AEST.localize(dt)
                else:
                    dt = dt.astimezone(AEST)
            else:
                dt = datetime.fromisoformat(timestamp_str)
                if dt.tzinfo is None:
                    dt = AEST.localize(dt)
            return dt
        return None
    except (ValueError, AttributeError) as e:
        print(f"[WARNING] Failed to parse timestamp {timestamp_str}: {e}")
        return None


def fetch_region_data(client, region: str, hours_back: int = 48) -> Dict:
    """
    Fetch historical and forecast price data for a region from MongoDB
    
    Returns:
        Dictionary with 'historical' and 'forecast' lists of (timestamp, price) tuples
    """
    db = client[DB_NAME]
    collection = db[PRICE_COLLECTION_NAME]
    
    # Calculate time range (last 48 hours)
    cutoff_time = datetime.now(AEST) - timedelta(hours=hours_back)
    cutoff_iso = cutoff_time.isoformat()
    
    # Query MongoDB for this region
    query = {
        'region': region,
        'timestamp': {'$gte': cutoff_iso}
    }
    
    documents = collection.find(query).sort('timestamp', 1)
    
    historical_data = []
    forecast_data = []
    
    for doc in documents:
        timestamp_str = doc.get('timestamp')
        if not timestamp_str:
            continue
        
        dt = parse_timestamp(timestamp_str)
        if dt is None:
            continue
        
        # Convert to naive datetime for matplotlib
        dt_naive = dt.replace(tzinfo=None)
        
        # Extract historical price
        historical_price_obj = doc.get('historical_price')
        if historical_price_obj and isinstance(historical_price_obj, dict):
            historical_price_value = historical_price_obj.get('price')
            if historical_price_value is not None:
                historical_data.append((dt_naive, float(historical_price_value)))
        
        # Extract forecast price
        forecast_price = doc.get('Forecast_Price')
        if forecast_price is not None:
            forecast_data.append((dt_naive, float(forecast_price)))
    
    return {
        'historical': historical_data,
        'forecast': forecast_data
    }


def create_chart():
    """Create a chart showing historical and forecast prices for 4 states"""
    print("="*80)
    print("CHECK CHART - Historical & Forecast Prices from MongoDB")
    print("="*80)
    print()
    
    # Connect to MongoDB
    print("[INFO] Connecting to MongoDB...")
    client = connect_mongo()
    if not client:
        print("[ERROR] Failed to connect to MongoDB")
        return None
    
    print("[OK] Connected to MongoDB")
    print()
    
    # Fetch data for all regions
    all_data = {}
    for region in REGIONS:
        print(f"[INFO] Fetching data for {region} ({REGION_NAMES[region]})...")
        region_data = fetch_region_data(client, region, hours_back=48)
        
        # Filter forecast: remove any forecast points that have the same timestamp as historical data
        historical = region_data['historical']
        forecast = region_data['forecast']
        
        # Create a set of historical timestamps for fast lookup
        historical_timestamps = {dt for dt, _ in historical} if historical else set()
        
        # Filter forecast to only include timestamps not in historical
        filtered_forecast = [(dt, price) for dt, price in forecast if dt not in historical_timestamps] if forecast else []
        
        # Update region_data with filtered forecast
        region_data['forecast'] = filtered_forecast
        all_data[region] = region_data
        
        hist_count = len(historical)
        forecast_count = len(forecast)
        filtered_count = len(filtered_forecast)
        print(f"  [OK] Found {hist_count} historical points, {forecast_count} forecast points ({filtered_count} after filtering)")
    
    client.close()
    print()
    
    # Create figure with subplots (2x2 grid for 4 states)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Historical & Forecast Electricity Prices\nNEM Regions (Last 48 Hours)',
                 fontsize=16, fontweight='bold', y=0.995)
    
    # Flatten axes array for easier iteration
    axes_flat = axes.flatten()
    
    # Plot each region
    for idx, region in enumerate(REGIONS):
        ax = axes_flat[idx]
        region_data = all_data[region]
        
        historical = region_data['historical']
        forecast = region_data['forecast']  # Already filtered
        
        # Plot historical prices
        if historical:
            hist_times, hist_prices = zip(*historical)
            ax.plot(hist_times, hist_prices,
                   marker='o', markersize=4, linestyle='-', linewidth=2,
                   color='#2E86AB', label='Historical', alpha=0.8)
        else:
            ax.text(0.5, 0.5, 'No historical data', 
                   transform=ax.transAxes, ha='center', va='center',
                   fontsize=10, style='italic', color='gray')
        
        # Plot forecast prices (only for timestamps without historical data)
        if forecast:
            forecast_times, forecast_prices = zip(*forecast)
            ax.plot(forecast_times, forecast_prices,
                   marker='s', markersize=4, linestyle='--', linewidth=2,
                   color='#F18F01', label='Forecast', alpha=0.8)
        
        # Format subplot
        ax.set_title(f'{REGION_NAMES[region]} ({region})', fontsize=12, fontweight='bold')
        ax.set_xlabel('Time', fontsize=10)
        ax.set_ylabel('Price ($/MWh)', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best', fontsize=9)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add horizontal line at $0
        ax.axhline(y=0, color='red', linestyle=':', linewidth=1, alpha=0.5)
        
        # Add statistics text
        if historical or forecast:
            stats_text = []
            if historical:
                hist_prices_list = [p for _, p in historical]
                stats_text.append(f"Hist: ${min(hist_prices_list):.0f}-${max(hist_prices_list):.0f}/MWh")
            if forecast:
                forecast_prices_list = [p for _, p in forecast]
                stats_text.append(f"Forecast: ${min(forecast_prices_list):.0f}-${max(forecast_prices_list):.0f}/MWh")
            
            if stats_text:
                ax.text(0.02, 0.98, '\n'.join(stats_text),
                       transform=ax.transAxes, fontsize=8,
                       verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    
    # Save the chart
    output_file = Path(__file__).parent / "Check_Chart.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[OK] Chart saved to {output_file}")
    
    # Display summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for region in REGIONS:
        region_data = all_data[region]
        historical = region_data['historical']
        forecast = region_data['forecast']
        
        print(f"\n{REGION_NAMES[region]} ({region}):")
        
        if historical:
            hist_prices = [p for _, p in historical]
            hist_times = [t for t, _ in historical]
            print(f"  Historical: {len(historical)} points")
            print(f"    Time range: {hist_times[0].strftime('%Y-%m-%d %H:%M')} to {hist_times[-1].strftime('%Y-%m-%d %H:%M')}")
            print(f"    Min: ${min(hist_prices):.2f}/MWh, Max: ${max(hist_prices):.2f}/MWh, Avg: ${sum(hist_prices)/len(hist_prices):.2f}/MWh")
        else:
            print(f"  Historical: No data")
        
        if forecast:
            forecast_prices = [p for _, p in forecast]
            forecast_times = [t for t, _ in forecast]
            print(f"  Forecast: {len(forecast)} points")
            print(f"    Time range: {forecast_times[0].strftime('%Y-%m-%d %H:%M')} to {forecast_times[-1].strftime('%Y-%m-%d %H:%M')}")
            print(f"    Min: ${min(forecast_prices):.2f}/MWh, Max: ${max(forecast_prices):.2f}/MWh, Avg: ${sum(forecast_prices)/len(forecast_prices):.2f}/MWh")
        else:
            print(f"  Forecast: No data")
    
    print("\n" + "="*80)
    
    return output_file


if __name__ == '__main__':
    try:
        create_chart()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Failed to create chart: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

