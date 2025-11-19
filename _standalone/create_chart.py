"""
Create a visualization chart for power prices
"""

import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path

# Load the cached data
CACHE_FILE = Path(__file__).parent / "nem_price_cache.json"

def load_cache():
    """Load the unified cache file"""
    with open(CACHE_FILE, 'r') as f:
        return json.load(f)

def create_price_chart():
    """Create a chart showing dispatch, P5MIN, and predispatch prices"""
    cache = load_cache()

    # Prepare data for plotting
    datasets = {}

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache and cache[data_type]:
            # Get the latest timestamp
            latest_timestamp = max(cache[data_type].keys())
            data = cache[data_type][latest_timestamp]

            print(f"\n[DEBUG] {data_type.upper()}:")
            print(f"  Using timestamp key: {latest_timestamp}")
            print(f"  Source file: {data.get('source_file', 'N/A')}")
            print(f"  Number of prices: {len(data.get('prices', []))}")

            # Extract timestamps and prices
            timestamps = []
            prices = []

            for point in data.get('prices', []):
                # Parse ISO timestamp and convert to naive datetime
                # (remove timezone to prevent matplotlib from converting it)
                dt = datetime.fromisoformat(point['timestamp'])
                # Convert to naive datetime by replacing tzinfo with None
                dt_naive = dt.replace(tzinfo=None)
                timestamps.append(dt_naive)
                prices.append(point['price'])

            if timestamps and prices:
                print(f"  Time range: {timestamps[0].strftime('%Y-%m-%d %H:%M')} to {timestamps[-1].strftime('%Y-%m-%d %H:%M')}")
                datasets[data_type] = {
                    'timestamps': timestamps,
                    'prices': prices,
                    'label': data_type.upper(),
                    'source': data.get('source_file', '')
                }

    # Create the plot
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot each dataset
    colors = {'dispatch': '#2E86AB', 'p5min': '#A23B72', 'predispatch': '#F18F01'}
    markers = {'dispatch': 'o', 'p5min': 's', 'predispatch': '^'}

    for data_type, data in datasets.items():
        ax.plot(data['timestamps'], data['prices'],
                marker=markers.get(data_type, 'o'),
                linestyle='-',
                linewidth=2,
                markersize=6,
                color=colors.get(data_type, 'blue'),
                label=f"{data['label']} ({len(data['prices'])} points)",
                alpha=0.8)

    # Format the chart
    ax.set_xlabel('Time (AEDT)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Price ($/MWh)', fontsize=12, fontweight='bold')
    ax.set_title('Victoria (VIC1) Electricity Spot Prices\nNEMweb Data',
                 fontsize=14, fontweight='bold', pad=20)

    # Format x-axis to show time values clearly
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45, ha='right')

    # Ensure x-axis uses the actual data timestamps
    plt.gcf().autofmt_xdate()

    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Add legend
    ax.legend(loc='best', framealpha=0.9, fontsize=10)

    # Add horizontal line at $0
    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='$0/MWh')

    # Tight layout
    plt.tight_layout()

    # Save the chart
    output_file = Path(__file__).parent / "price_comparison.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[OK] Chart saved to {output_file}")

    # Display summary
    print("\n" + "="*60)
    print("PRICE SUMMARY")
    print("="*60)

    for data_type, data in datasets.items():
        prices = data['prices']
        if prices:
            print(f"\n{data['label']}:")
            print(f"  Current/Latest: ${prices[-1]:.2f}/MWh")
            print(f"  Min: ${min(prices):.2f}/MWh")
            print(f"  Max: ${max(prices):.2f}/MWh")
            print(f"  Avg: ${sum(prices)/len(prices):.2f}/MWh")
            print(f"  Data points: {len(prices)}")

    return output_file

if __name__ == '__main__':
    create_price_chart()
