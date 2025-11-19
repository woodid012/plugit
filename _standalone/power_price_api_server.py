"""
Flask API Server for NEMweb Price Data
Serves price data for real-time chart updates
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import sys
from pathlib import Path

# Add power_price directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'power_price'))
from fetch_prices import (
    fetch_dispatch_prices,
    fetch_p5min_prices,
    fetch_predispatch_prices,
    get_latest_cached_data,
    export_for_api
)
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

AEST = pytz.timezone('Australia/Sydney')


@app.route('/api/prices/latest')
def get_latest_prices():
    """
    Get latest cached price data from all sources
    Returns: JSON with separate arrays for each data type

    NOTE: NEMweb data is in AEST (UTC+10) but we shift it by +1 hour
    for AEDT (UTC+11) display on charts
    """
    from datetime import timedelta

    data = get_latest_cached_data()

    # Format for Chart.js
    result = {
        'metadata': data['metadata'],
        'series': []
    }

    for data_type, dataset in data['data'].items():
        if 'prices' in dataset:
            # Shift timestamps by +1 hour (AEST to AEDT conversion)
            shifted_data = []
            for p in dataset['prices']:
                # Parse timestamp and add 1 hour
                timestamp_dt = datetime.fromisoformat(p['timestamp'])
                shifted_dt = timestamp_dt + timedelta(hours=1)
                shifted_data.append({
                    'x': shifted_dt.isoformat(),
                    'y': p['price']
                })

            result['series'].append({
                'name': data_type,
                'data': shifted_data,
                'label': {
                    'dispatch': 'Dispatch (Historical)',
                    'p5min': 'P5MIN (5-min Forecast)',
                    'predispatch': 'Predispatch (Full Forecast)'
                }.get(data_type, data_type)
            })

    return jsonify(result)


@app.route('/api/prices/all')
def get_all_prices():
    """
    Get all cached prices in flat format (for database export)
    """
    return jsonify(export_for_api())


@app.route('/api/prices/current')
def get_current_price():
    """
    Get the current 5-minute interval price

    NOTE: NEMweb data is in AEST (UTC+10) but we display as AEDT (UTC+11)
    So we subtract 1 hour from current time to find the data, then display
    the AEDT time to the user
    """
    from datetime import timedelta

    # Current time in AEDT
    now_aedt = datetime.now(AEST)
    current_minute = now_aedt.minute
    interval_minute = (current_minute // 5) * 5
    current_interval_aedt = now_aedt.replace(minute=interval_minute, second=0, microsecond=0)

    # Convert to AEST for data lookup (subtract 1 hour)
    current_interval_aest = current_interval_aedt - timedelta(hours=1)

    # Get latest data and find price at current interval (in AEST)
    data = get_latest_cached_data()
    current_price = None
    current_source = None

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in data['data']:
            for price_point in data['data'][data_type].get('prices', []):
                if price_point['timestamp'].startswith(current_interval_aest.strftime('%Y-%m-%d %H:%M')):
                    current_price = price_point['price']
                    current_source = data_type
                    break
        if current_price:
            break

    # Return AEDT timestamp for display
    return jsonify({
        'timestamp': current_interval_aedt.isoformat(),
        'price': current_price,
        'source': current_source,
        'fetched_at': datetime.now(AEST).isoformat()
    })


@app.route('/api/cache/status')
def cache_status():
    """
    Get cache health status - shows data freshness
    """
    from fetch_prices import load_unified_cache, is_data_stale

    cache = load_unified_cache()
    now = datetime.now(AEST)

    status = {
        'current_time': now.isoformat(),
        'cache_updated': cache.get('metadata', {}).get('last_updated', None),
        'data_sources': {}
    }

    for data_type in ['dispatch', 'p5min', 'predispatch']:
        if data_type in cache and cache[data_type]:
            latest_key = max(cache[data_type].keys())

            # Parse timestamp
            try:
                year = int(latest_key[0:4])
                month = int(latest_key[4:6])
                day = int(latest_key[6:8])
                hour = int(latest_key[8:10])
                minute = int(latest_key[10:12])
                data_time = AEST.localize(datetime(year, month, day, hour, minute))
                age_minutes = (now - data_time).total_seconds() / 60

                status['data_sources'][data_type] = {
                    'timestamp': latest_key,
                    'datetime': data_time.isoformat(),
                    'age_minutes': round(age_minutes, 1),
                    'is_stale': is_data_stale(latest_key, max_age_hours=6),
                    'status': 'stale' if is_data_stale(latest_key, max_age_hours=6) else 'fresh'
                }
            except:
                status['data_sources'][data_type] = {
                    'timestamp': latest_key,
                    'error': 'Could not parse timestamp'
                }
        else:
            status['data_sources'][data_type] = {
                'status': 'no_data'
            }

    return jsonify(status)


@app.route('/api/refresh')
def refresh_data():
    """
    Fetch fresh data from NEMweb (use sparingly - every 5 minutes max)
    Smart retry logic: won't save if fetched data is older than cached data
    """
    from fetch_prices import load_unified_cache

    try:
        # Get current cache state before refresh
        cache_before = load_unified_cache()
        before_timestamps = {
            data_type: max(cache_before[data_type].keys()) if cache_before.get(data_type) else None
            for data_type in ['dispatch', 'p5min', 'predispatch']
        }

        # Fetch new data
        dispatch = fetch_dispatch_prices(region='VIC1', hours_back=1, force_refresh=True)
        p5min = fetch_p5min_prices(region='VIC1', hours_ahead=0, force_refresh=True)
        predispatch = fetch_predispatch_prices(region='VIC1', hours_ahead=24, force_refresh=True)

        # Check what actually got updated
        cache_after = load_unified_cache()
        after_timestamps = {
            data_type: max(cache_after[data_type].keys()) if cache_after.get(data_type) else None
            for data_type in ['dispatch', 'p5min', 'predispatch']
        }

        results = {}
        warnings = []

        for data_type in ['dispatch', 'p5min', 'predispatch']:
            before = before_timestamps[data_type]
            after = after_timestamps[data_type]

            if after and after != before:
                results[data_type] = {
                    'status': 'updated',
                    'new_timestamp': after,
                    'old_timestamp': before
                }
            elif after and after == before:
                results[data_type] = {
                    'status': 'unchanged',
                    'timestamp': after
                }
            elif before and not after:
                # This shouldn't happen (data disappeared?)
                results[data_type] = {
                    'status': 'warning',
                    'message': 'Data disappeared from cache'
                }
                warnings.append(f'{data_type}: data disappeared')
            elif not after:
                results[data_type] = {
                    'status': 'failed',
                    'message': 'No data fetched'
                }
                warnings.append(f'{data_type}: fetch failed')

        return jsonify({
            'status': 'success' if not warnings else 'partial_success',
            'refreshed_at': datetime.now(AEST).isoformat(),
            'results': results,
            'warnings': warnings if warnings else None
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/')
def index():
    """
    Simple dashboard with real-time chart
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VIC1 Power Prices - Live</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/luxon@3"></script>
        <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2E86AB;
                margin-bottom: 10px;
            }
            .status {
                padding: 10px;
                background: #e8f5e9;
                border-left: 4px solid #4caf50;
                margin-bottom: 20px;
            }
            .current-price {
                font-size: 48px;
                font-weight: bold;
                color: #E63946;
                display: inline-block;
                margin-right: 20px;
            }
            .price-label {
                color: #666;
                font-size: 14px;
            }
            #chart-container {
                position: relative;
                height: 500px;
            }
            .last-update {
                color: #999;
                font-size: 12px;
                text-align: right;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>VIC1 Electricity Prices - Live Dashboard</h1>

            <div class="status">
                <div class="price-label">Current Price (5-min interval)</div>
                <div>
                    <span class="current-price" id="current-price">--</span>
                    <span style="color: #666;">AUD/MWh</span>
                    <span style="color: #999; font-size: 14px; margin-left: 20px;" id="current-time">--</span>
                </div>
            </div>

            <div id="chart-container">
                <canvas id="priceChart"></canvas>
            </div>

            <div class="last-update">
                Last updated: <span id="last-update">--</span>
            </div>
        </div>

        <script>
            let chart = null;
            const ctx = document.getElementById('priceChart').getContext('2d');

            // Initialize chart
            function initChart(data) {
                const datasets = data.series.map((series, index) => {
                    const colors = {
                        'dispatch': { border: '#2E86AB', bg: 'rgba(46, 134, 171, 0.1)', marker: 'circle' },
                        'p5min': { border: '#A23B72', bg: 'rgba(162, 59, 114, 0.1)', marker: 'rect' },
                        'predispatch': { border: '#F18F01', bg: 'rgba(241, 143, 1, 0.1)', marker: 'triangle' }
                    };

                    const color = colors[series.name] || { border: '#999', bg: 'rgba(150, 150, 150, 0.1)' };

                    return {
                        label: series.label,
                        data: series.data,
                        borderColor: color.border,
                        backgroundColor: color.bg,
                        pointStyle: color.marker,
                        pointRadius: series.name === 'dispatch' ? 8 : 4,
                        borderWidth: 2,
                        fill: false,
                        tension: 0.1
                    };
                });

                if (chart) {
                    chart.destroy();
                }

                chart = new Chart(ctx, {
                    type: 'line',
                    data: { datasets },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            x: {
                                type: 'time',
                                time: {
                                    unit: 'hour',
                                    displayFormats: {
                                        hour: 'HH:mm'
                                    }
                                },
                                title: {
                                    display: true,
                                    text: 'Time (AEDT)'
                                }
                            },
                            y: {
                                title: {
                                    display: true,
                                    text: 'Price (AUD/MWh)'
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false
                            }
                        }
                    }
                });
            }

            // Update current price
            async function updateCurrentPrice() {
                try {
                    const response = await fetch('/api/prices/current');
                    const data = await response.json();

                    if (data.price !== null) {
                        document.getElementById('current-price').textContent = data.price.toFixed(2);
                        document.getElementById('current-time').textContent =
                            new Date(data.timestamp).toLocaleTimeString('en-AU', {
                                hour: '2-digit',
                                minute: '2-digit',
                                timeZone: 'Australia/Sydney'
                            });
                    }
                } catch (error) {
                    console.error('Error updating current price:', error);
                }
            }

            // Update chart data
            async function updateChart() {
                try {
                    const response = await fetch('/api/prices/latest');
                    const data = await response.json();

                    initChart(data);

                    const now = new Date().toLocaleString('en-AU', {
                        timeZone: 'Australia/Sydney',
                        hour12: false
                    });
                    document.getElementById('last-update').textContent = now;
                } catch (error) {
                    console.error('Error updating chart:', error);
                }
            }

            // Initial load
            updateChart();
            updateCurrentPrice();

            // Auto-refresh every 30 seconds
            setInterval(() => {
                updateChart();
                updateCurrentPrice();
            }, 30000);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)


if __name__ == '__main__':
    print("="*60)
    print("NEMweb Price API Server")
    print("="*60)
    print("Dashboard: http://localhost:5000")
    print("API Endpoints:")
    print("  /api/prices/latest  - Latest cached data (optimized for charts)")
    print("  /api/prices/all     - All cached data (flat format)")
    print("  /api/prices/current - Current 5-min interval price")
    print("  /api/refresh        - Fetch fresh data from NEMweb")
    print("="*60)
    print()

    app.run(debug=True, host='0.0.0.0', port=5000)
