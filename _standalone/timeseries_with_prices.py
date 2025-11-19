"""
Create a timeseries visualization showing device power consumption and electricity prices
"""

import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path
import numpy as np

# File paths
TIMESERIES_FILE = Path(__file__).parent.parent / "timeseries_data.json"
PRICE_CACHE_FILE = Path(__file__).parent / "nem_price_cache.json"

def load_timeseries_data():
    """Load device power consumption timeseries data"""
    with open(TIMESERIES_FILE, 'r') as f:
        return json.load(f)

def load_price_cache():
    """Load NEM price cache data"""
    with open(PRICE_CACHE_FILE, 'r') as f:
        return json.load(f)

def extract_all_prices(cache):
    """Extract all available prices from all data types and timestamps"""
    all_prices = []

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache:
            for timestamp_key, data in cache[data_type].items():
                for point in data.get('prices', []):
                    # Parse timestamp and convert to naive datetime
                    dt = datetime.fromisoformat(point['timestamp'])
                    dt_naive = dt.replace(tzinfo=None)
                    all_prices.append({
                        'timestamp': dt_naive,
                        'price': point['price'],
                        'type': data_type
                    })

    # Sort by timestamp
    all_prices.sort(key=lambda x: x['timestamp'])

    return all_prices

def create_combined_plot():
    """Create a combined plot showing power consumption and electricity prices"""
    # Load data
    timeseries_data = load_timeseries_data()
    price_cache = load_price_cache()

    # Extract all prices
    all_prices = extract_all_prices(price_cache)

    if not all_prices:
        print("[ERROR] No price data available")
        return

    print(f"\n[INFO] Found {len(all_prices)} price data points")
    print(f"[INFO] Price time range: {all_prices[0]['timestamp']} to {all_prices[-1]['timestamp']}")

    # Get time range from timeseries data
    all_timestamps = []
    for device_id, device_data in timeseries_data.items():
        for point in device_data['data']:
            ts = datetime.fromisoformat(point['timestamp'])
            all_timestamps.append(ts)

    if not all_timestamps:
        print("[ERROR] No timeseries data available")
        return

    min_time = min(all_timestamps)
    max_time = max(all_timestamps)

    print(f"[INFO] Device data time range: {min_time} to {max_time}")

    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(16, 8))

    # Color palette for devices
    colors = plt.cm.tab10(np.linspace(0, 1, len(timeseries_data)))

    # Plot device power consumption on first y-axis
    for idx, (device_id, device_data) in enumerate(timeseries_data.items()):
        device_name = device_data.get('name', device_id)
        timestamps = []
        power_values = []

        for point in device_data['data']:
            ts = datetime.fromisoformat(point['timestamp'])
            timestamps.append(ts)
            power_values.append(point['power'])

        # Only plot if there's some non-zero data
        if any(p > 0 for p in power_values):
            ax1.plot(timestamps, power_values,
                    label=device_name,
                    color=colors[idx],
                    alpha=0.7,
                    linewidth=1.5)

    ax1.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Power Consumption (W)', fontsize=12, fontweight='bold', color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.grid(True, alpha=0.3, linestyle='--')

    # Create second y-axis for electricity prices
    ax2 = ax1.twinx()

    # Filter prices to match timeseries time range (with some buffer)
    from datetime import timedelta
    buffer = timedelta(hours=1)
    filtered_prices = [p for p in all_prices
                      if min_time - buffer <= p['timestamp'] <= max_time + buffer]

    if filtered_prices:
        print(f"[INFO] Plotting {len(filtered_prices)} price points in device time range")

        # Group by data type for different visual styles
        price_types = {}
        for p in filtered_prices:
            if p['type'] not in price_types:
                price_types[p['type']] = {'timestamps': [], 'prices': []}
            price_types[p['type']]['timestamps'].append(p['timestamp'])
            price_types[p['type']]['prices'].append(p['price'])

        # Plot each price type
        price_colors = {'dispatch': '#E63946', 'p5min': '#F77F00', 'predispatch': '#06D6A0'}
        price_markers = {'dispatch': 'o', 'p5min': 's', 'predispatch': '^'}
        price_labels = {'dispatch': 'Dispatch', 'p5min': 'P5MIN', 'predispatch': 'Pre-dispatch'}

        for price_type, data in price_types.items():
            ax2.plot(data['timestamps'], data['prices'],
                    label=f"Price ({price_labels.get(price_type, price_type)})",
                    color=price_colors.get(price_type, 'red'),
                    marker=price_markers.get(price_type, 'o'),
                    markersize=4,
                    linestyle='-',
                    linewidth=2,
                    alpha=0.8)

        ax2.set_ylabel('Electricity Price ($/MWh)', fontsize=12, fontweight='bold', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        # Add horizontal line at $0
        ax2.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5)
    else:
        print("[WARNING] No price data overlaps with device timeseries data")
        ax2.set_ylabel('Electricity Price ($/MWh)', fontsize=12, fontweight='bold', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

    # Format x-axis
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45, ha='right')

    # Title
    plt.title('Device Power Consumption & Electricity Prices\nVictoria (VIC1) Region',
             fontsize=14, fontweight='bold', pad=20)

    # Legends
    # Combine both legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    if lines1 or lines2:
        # Place legend outside plot area
        ax1.legend(lines1 + lines2, labels1 + labels2,
                  loc='upper left', bbox_to_anchor=(0, -0.15),
                  ncol=3, framealpha=0.9, fontsize=9)

    # Tight layout
    plt.tight_layout()

    # Save the chart
    output_file = Path(__file__).parent / "timeseries_with_prices.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n[OK] Chart saved to {output_file}")

    # Display summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    # Device summary
    print(f"\nDevice Data:")
    print(f"  Devices: {len(timeseries_data)}")
    print(f"  Time range: {min_time.strftime('%Y-%m-%d %H:%M')} to {max_time.strftime('%Y-%m-%d %H:%M')}")

    for device_id, device_data in timeseries_data.items():
        power_values = [p['power'] for p in device_data['data']]
        if any(p > 0 for p in power_values):
            avg_power = sum(power_values) / len(power_values)
            max_power = max(power_values)
            print(f"  - {device_data.get('name', device_id)}: Avg={avg_power:.1f}W, Max={max_power:.1f}W")

    # Price summary
    if filtered_prices:
        prices = [p['price'] for p in filtered_prices]
        print(f"\nPrice Data (in device time range):")
        print(f"  Data points: {len(filtered_prices)}")
        print(f"  Min: ${min(prices):.2f}/MWh")
        print(f"  Max: ${max(prices):.2f}/MWh")
        print(f"  Avg: ${sum(prices)/len(prices):.2f}/MWh")

    return output_file

if __name__ == '__main__':
    create_combined_plot()
