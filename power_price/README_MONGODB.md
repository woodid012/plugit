# MongoDB Sync for NEMweb Power Prices

This script syncs NEMweb power price data to MongoDB for all Australian NEM regions.

## Overview

The `mongodb_sync.py` script:
- Fetches historical dispatch prices, 5-minute predispatch, and 30-minute predispatch data
- Processes data for all NEM regions: VIC1, NSW1, QLD1, SA1, TAS1
- Stores data in MongoDB with priority-based `Export_Price` field
- Uses latest file timestamps to determine if updates are needed
- Overwrites existing data if newer files are available

## Data Priority

The `Export_Price` field uses the following priority order:
1. **Historical Price** (dispatch) - Actual historical settlement prices
2. **Dispatch 5 Minute** (p5min) - Short-term 5-minute forecasts
3. **Dispatch 30 Minute** (predispatch) - Longer-term 30-minute forecasts

If a higher priority source exists, it's used; otherwise, the next available source is used.

## MongoDB Structure

### Database: `nem_prices`
### Collection: `price_data`

### Document Schema:
```json
{
  "region": "VIC1",
  "timestamp": "2025-11-18T20:20:00+11:00",
  "historical_price": {
    "price": 66.26,
    "source_file": "PUBLIC_DISPATCH_202511182020_...",
    "file_timestamp": "202511182020",
    "fetched_at": "2025-11-18T21:20:43+11:00"
  },
  "dispatch_5min": {
    "price": 69.67,
    "source_file": "PUBLIC_P5MIN_202511182020_...",
    "file_timestamp": "202511182020",
    "fetched_at": "2025-11-18T21:20:44+11:00"
  },
  "dispatch_30min": {
    "price": 75.08,
    "source_file": "PUBLIC_PREDISPATCH_202511182030_...",
    "file_timestamp": "202511182030",
    "fetched_at": "2025-11-18T21:20:45+11:00"
  },
  "Export_Price": 66.26,
  "last_updated": "2025-11-18T21:30:00+11:00"
}
```

### Indexes:
- Unique compound index on `(region, timestamp)`
- Index on `timestamp` for time-based queries
- Index on `region` for region-based queries

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. MongoDB connection is configured in the script with:
   - Username: `NEMprice`
   - Password: `test_smart123`
   - URI: `mongodb+srv://NEMprice:test_smart123@cluster0.tm9wpue.mongodb.net/?appName=Cluster0`

## Usage

### Basic Sync
```bash
python power_price/mongodb_sync.py
```

### Force Refresh (re-fetch all data)
```bash
python power_price/mongodb_sync.py --refresh
# or
python power_price/mongodb_sync.py -r
```

## Update Logic

The script implements smart update logic:
1. **Latest File Detection**: Extracts timestamp from source filenames (YYYYMMDDHHMM format)
2. **Comparison**: Compares file timestamps to determine if data is newer
3. **Overwrite Policy**: 
   - If new file timestamp >= existing file timestamp → Update
   - If new file timestamp < existing file timestamp → Skip (preserve newer data)
4. **Per-Timestamp Updates**: Each price timestamp is checked individually

## GitHub Actions Automation

To run every 30 minutes using GitHub Actions, create `.github/workflows/sync-prices.yml`:

```yaml
name: Sync NEM Prices to MongoDB

on:
  schedule:
    - cron: '*/30 * * * *'  # Every 30 minutes
  workflow_dispatch:  # Allow manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r power_price/requirements.txt
      
      - name: Sync to MongoDB
        run: |
          python power_price/mongodb_sync.py
        env:
          # Add any required environment variables here
```

## Data Sources

The script fetches from three NEMweb sources:
1. **Dispatch Reports** (`DISPATCH_REPORTS_URL`): Historical settlement prices
2. **P5 Reports** (`P5_REPORTS_URL`): 5-minute predispatch forecasts
3. **Predispatch Reports** (`PREDISPATCH_REPORTS_URL`): 30-minute predispatch forecasts

## Regions Supported

- **VIC1**: Victoria
- **NSW1**: New South Wales
- **QLD1**: Queensland
- **SA1**: South Australia
- **TAS1**: Tasmania

## Error Handling

The script:
- Continues processing other regions if one fails
- Logs all errors for review
- Returns exit code 1 if any errors occurred
- Provides summary of inserted/updated/skipped records

## Output

The script provides detailed console output:
- Connection status
- Fetch progress for each region and data type
- Sync statistics (inserted/updated/skipped)
- Error summary

## Notes

- The script uses the existing `fetch_prices.py` module for data fetching
- Data is cached locally before syncing to MongoDB
- Timezone handling uses `Australia/Sydney` (AEST/AEDT)
- File timestamps are extracted from NEMweb filenames

