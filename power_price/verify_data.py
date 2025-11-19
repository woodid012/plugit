"""
Verify data in MongoDB after sync and generate charts
"""
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pytz
from collections import defaultdict

uri = "mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0"
client = MongoClient(uri, server_api=ServerApi('1'))

db = client['nem_prices']
collection = db['price_data']

# Count documents
total = collection.count_documents({})
print(f"📊 Total documents: {total}")

# Count by region
print("\n📈 Documents by region:")
for region in ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']:
    count = collection.count_documents({'region': region})
    print(f"  {region}: {count}")

# Show a sample document
print("\n📄 Sample document:")
sample = collection.find_one()
if sample:
    # Remove _id for cleaner output
    sample.pop('_id', None)
    print(json.dumps(sample, indent=2, default=str))
else:
    print("  (no documents found)")

# Check Export_Price calculation
print("\n💰 Export_Price statistics:")
with_export = collection.count_documents({'Export_Price': {'$ne': None}})
without_export = collection.count_documents({'Export_Price': None})
print(f"  Documents with Export_Price: {with_export}")
print(f"  Documents without Export_Price: {without_export}")

# Latest timestamps by region
print("\n🕐 Latest timestamps by region:")
for region in ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']:
    latest = collection.find_one(
        {'region': region},
        sort=[('timestamp', -1)]
    )
    if latest:
        export_price = latest.get('Export_Price', 'N/A')
        print(f"  {region}: {latest.get('timestamp')} (Export_Price: {export_price})")
    else:
        print(f"  {region}: (no data)")

# Data type availability
print("\n📊 Data type availability:")
for region in ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']:
    has_historical = collection.count_documents({
        'region': region,
        'historical_price': {'$ne': None}
    })
    has_5min = collection.count_documents({
        'region': region,
        'dispatch_5min': {'$ne': None}
    })
    has_30min = collection.count_documents({
        'region': region,
        'dispatch_30min': {'$ne': None}
    })
    print(f"  {region}:")
    print(f"    Historical: {has_historical}")
    print(f"    5-min: {has_5min}")
    print(f"    30-min: {has_30min}")

# Generate charts
print("\n📊 Generating charts...")

try:
    # Parse timestamps and prepare data for plotting
    regions_data = defaultdict(list)
    all_regions_times = defaultdict(list)
    all_regions_prices = defaultdict(list)
    
    # Fetch recent data (last 48 hours worth)
    for region in ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']:
        docs = list(collection.find(
            {
                'region': region,
                'Export_Price': {'$ne': None}
            },
            sort=[('timestamp', 1)]
        ).limit(1000))  # Limit to recent 1000 points per region
        
        if docs:
            times = []
            prices = []
            historical_prices = []
            p5min_prices = []
            p30min_prices = []
            
            for doc in docs:
                try:
                    # Parse timestamp (handle both ISO format and string)
                    ts_str = doc.get('timestamp', '')
                    if isinstance(ts_str, str):
                        # Try parsing ISO format
                        if 'T' in ts_str:
                            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        else:
                            continue
                    else:
                        continue
                    
                    # Convert to AEST for consistency
                    AEST = pytz.timezone('Australia/Sydney')
                    if dt.tzinfo is None:
                        dt = AEST.localize(dt)
                    else:
                        dt = dt.astimezone(AEST)
                    
                    export_price = doc.get('Export_Price')
                    if export_price is not None:
                        times.append(dt)
                        prices.append(float(export_price))
                        
                        # Get individual source prices for comparison
                        hist = doc.get('historical_price', {})
                        p5 = doc.get('dispatch_5min', {})
                        p30 = doc.get('dispatch_30min', {})
                        
                        historical_prices.append(float(hist.get('price')) if hist and hist.get('price') else None)
                        p5min_prices.append(float(p5.get('price')) if p5 and p5.get('price') else None)
                        p30min_prices.append(float(p30.get('price')) if p30 and p30.get('price') else None)
                        
                except Exception as e:
                    continue
            
            if times and prices:
                regions_data[region] = {
                    'times': times,
                    'prices': prices,
                    'historical': historical_prices,
                    'p5min': p5min_prices,
                    'p30min': p30min_prices
                }
                all_regions_times[region] = times
                all_regions_prices[region] = prices
    
    if regions_data:
        # Create one chart for each region showing data source comparison
        colors = {'VIC1': 'blue', 'NSW1': 'red', 'QLD1': 'green', 'SA1': 'orange', 'TAS1': 'purple'}
        
        # Create a figure with subplots - one for each region
        num_regions = len(regions_data)
        if num_regions > 0:
            # Calculate grid size (2 columns, enough rows)
            cols = 2
            rows = (num_regions + 1) // 2  # Round up
            
            fig, axes = plt.subplots(rows, cols, figsize=(16, 6 * rows))
            if num_regions == 1:
                axes = [axes]
            else:
                axes = axes.flatten()
            
            region_list = ['VIC1', 'NSW1', 'QLD1', 'SA1', 'TAS1']
            chart_idx = 0
            
            for region in region_list:
                if region in regions_data:
                    data = regions_data[region]
                    ax = axes[chart_idx]
                    
                    if data['times']:
                        # Get timezone info from first timestamp
                        first_time = data['times'][0]
                        tz_name = first_time.tzname() if first_time.tzinfo else 'AEST'
                        
                        # Plot Export_Price line
                        ax.plot(data['times'], data['prices'], 
                                label='Export_Price', color='black', linewidth=2, alpha=0.8)
                        
                        # Plot individual sources where available
                        hist_times = [t for t, p in zip(data['times'], data['historical']) if p is not None]
                        hist_prices = [p for p in data['historical'] if p is not None]
                        if hist_times:
                            ax.scatter(hist_times, hist_prices, 
                                      label='Historical', color='blue', alpha=0.6, s=30, marker='o')
                        
                        p5_times = [t for t, p in zip(data['times'], data['p5min']) if p is not None]
                        p5_prices = [p for p in data['p5min'] if p is not None]
                        if p5_times:
                            ax.scatter(p5_times, p5_prices, 
                                      label='5-min Dispatch', color='green', alpha=0.6, s=30, marker='s')
                        
                        p30_times = [t for t, p in zip(data['times'], data['p30min']) if p is not None]
                        p30_prices = [p for p in data['p30min'] if p is not None]
                        if p30_times:
                            ax.scatter(p30_times, p30_prices, 
                                      label='30-min Dispatch', color='orange', alpha=0.6, s=30, marker='^')
                        
                        ax.set_title(f'Data Source Comparison - {region}', fontsize=14, fontweight='bold')
                        ax.set_xlabel(f'Time ({tz_name})', fontsize=10)
                        ax.set_ylabel('Price ($/MWh)', fontsize=10)
                        ax.legend(loc='best')
                        ax.grid(True, alpha=0.3)
                        
                        # Format x-axis with timestamp including timezone
                        # Use a format that shows date, time, and is readable
                        if len(data['times']) > 24:  # More than 24 hours of data
                            # Show date and time for longer periods
                            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
                            ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(data['times']) // 12)))
                        else:
                            # Show just time for shorter periods
                            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=max(5, len(data['times']) // 10)))
                        
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
                    
                    chart_idx += 1
            
            # Hide unused subplots
            for idx in range(chart_idx, len(axes)):
                axes[idx].set_visible(False)
            
            plt.tight_layout()
            
            # Save chart
            chart_filename = 'mongodb_price_charts.png'
            plt.savefig(chart_filename, dpi=150, bbox_inches='tight')
            print(f"✅ Charts saved to: {chart_filename}")
            
            # Show chart (if running interactively)
            try:
                plt.show()
            except:
                print("(Chart display not available in this environment)")
            
            plt.close()
    else:
        print("⚠️  No price data found to plot")
        
except Exception as e:
    print(f"⚠️  Error generating charts: {e}")
    import traceback
    traceback.print_exc()

client.close()
print("\n✅ Verification complete!")

