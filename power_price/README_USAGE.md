# VIC1 Power Price Dashboard - Usage Guide

## Quick Start

### 1. View the Dashboard (Standalone)

Simply open `index.html` in your browser:
```bash
# Windows
start index.html

# Or just double-click index.html
```

The dashboard will load data from `api_export.json` and auto-refresh every 30 seconds.

### 2. Fetch Latest Data

```bash
python fetch_prices.py --refresh
```

This will:
- Fetch from all 3 NEMweb sources (Dispatch, P5MIN, Predispatch)
- Save to unified cache: `nem_price_cache.json`
- **Smart validation**: Won't overwrite newer data with older data
- **Stale detection**: Warns if NEMweb is serving old cached files

### 3. Export for Dashboard

```bash
python -c "
from fetch_prices import export_for_api
import json

data = export_for_api()
with open('api_export.json', 'w') as f:
    json.dump(data, f, indent=2)
print('Data exported for dashboard')
"
```

## Smart Cache Features

### Protection Against Stale Data

The system now includes:

1. **Age Detection**
   - Warns if fetched data is >6 hours old
   - Shows data age: `Data age: 48.2 hours (from 2025-11-16 08:00)`

2. **No Overwriting**
   ```
   [WARNING] Fetched dispatch data (202511160800) is OLDER than cached data (202511182020)
   [INFO] Skipping save to prevent overwriting newer data
   ```

3. **Cache Validation**
   - Always compares timestamps before saving
   - Keeps the most recent 10 entries per data type
   - Auto-cleans old entries

## File Structure

```
power_price/
├── index.html              # Standalone dashboard (open in browser)
├── api_server.py           # Flask API server (for production)
├── fetch_prices.py         # Main data fetcher
├── nem_price_cache.json    # Unified cache (all data)
├── api_export.json         # Dashboard-ready export
└── requirements.txt        # Python dependencies
```

## API Endpoints (Flask Server)

Start the server:
```bash
python api_server.py
```

Then access:
- **Dashboard**: http://localhost:5000
- **Latest Data**: http://localhost:5000/api/prices/latest
- **Cache Status**: http://localhost:5000/api/cache/status
- **Refresh**: http://localhost:5000/api/refresh

### Cache Status Response
```json
{
  "current_time": "2025-11-18T21:52:00+11:00",
  "data_sources": {
    "dispatch": {
      "timestamp": "202511182020",
      "age_minutes": 92.3,
      "status": "fresh"
    },
    "p5min": {
      "timestamp": "202511182020",
      "age_minutes": 92.3,
      "status": "fresh"
    },
    "predispatch": {
      "timestamp": "202511182030",
      "age_minutes": 82.0,
      "status": "fresh"
    }
  }
}
```

## Scheduled Updates

For production, set up a cron job or Task Scheduler:

```bash
# Every 5 minutes
*/5 * * * * cd /path/to/power_price && python fetch_prices.py --refresh
```

This will:
1. Fetch latest from NEMweb
2. Validate timestamps
3. Update cache only if data is newer
4. Dashboard auto-refreshes from cache every 30s

## Data Format

### Unified Cache (`nem_price_cache.json`)
```json
{
  "metadata": {
    "last_updated": "2025-11-18T21:42:44...",
  },
  "dispatch": {
    "202511182020": { "region": "VIC1", "prices": [...] }
  },
  "p5min": {
    "202511182020": { "region": "VIC1", "prices": [...] }
  },
  "predispatch": {
    "202511182030": { "region": "VIC1", "prices": [...] }
  }
}
```

### API Export (`api_export.json`)
```json
{
  "metadata": {
    "total_records": 61,
    "exported_at": "2025-11-18T21:43:47..."
  },
  "prices": [
    {
      "timestamp": "2025-11-18T20:20:00+11:00",
      "price": 66.26,
      "data_type": "dispatch",
      "region": "VIC1"
    },
    ...
  ]
}
```

## Troubleshooting

### "Data is X hours old (stale)"
NEMweb is serving cached data. This is normal sometimes. The system will:
- Still save it if it's newer than what you have
- Skip it if you have newer data already
- Warn you about the age

### Dashboard shows no data
1. Check `api_export.json` exists
2. Run: `python -c "from fetch_prices import export_for_api; import json; json.dump(export_for_api(), open('api_export.json', 'w'))"`
3. Refresh browser

### Cache keeps old data
The cache keeps the 10 most recent entries per type. This is by design to prevent bloat while maintaining history.

## Next Steps

For production:
1. Deploy Flask API to cloud (Heroku, AWS, etc.)
2. Set up scheduled fetches (cron/Task Scheduler)
3. Point your main app to the API endpoints
4. Monitor `/api/cache/status` for data freshness
