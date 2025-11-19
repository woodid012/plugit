# MongoDB Sync for NEMweb Power Prices

This script syncs NEMweb power price data to MongoDB for all Australian NEM regions.

## Overview

The `mongodb_sync.py` script:
- Fetches historical dispatch prices, 5-minute predispatch, and 30-minute predispatch data
- Processes data for all NEM regions: VIC1, NSW1, QLD1, SA1, TAS1
- Stores data in MongoDB with priority-based `Export_Price` field
- Uses latest file timestamps to determine if updates are needed
- Overwrites existing data if newer files are available
- **Automatically cleans up forecast data older than 2 hours** and **deletes historical data older than 48 hours**

## Data Priority

The `Export_Price` field uses the following priority order:
1. **Historical Price** (dispatch) - Actual historical settlement prices
2. **Dispatch 5 Minute** (p5min) - Short-term 5-minute forecasts
3. **Dispatch 30 Minute** (predispatch) - Longer-term 30-minute forecasts

If a higher priority source exists, it's used; otherwise, the next available source is used.

## Data Retention Policy

- **Historical Dispatch Data**: Only last 48 hours are kept - older historical data is automatically deleted
- **5-Minute Forecast Data**: Only last 2 hours are kept - older forecast data is automatically removed
- **30-Minute Forecast Data**: Only last 2 hours are kept - older forecast data is automatically removed

The cleanup process runs automatically after each sync operation:
- Documents older than 48 hours are completely deleted (including `historical_price`)
- Documents between 2-48 hours old have forecast fields (`dispatch_5min`, `dispatch_30min`, `Forecast_Price`) removed but keep `historical_price`
- Documents newer than 2 hours keep all data

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

## Automated Scraping

The system supports two methods for automated scraping:

### Option 1: GitHub Actions (Cloud-Based)

A GitHub Actions workflow is already configured at `.github/workflows/sync-nem-prices.yml` that runs every 5 minutes.

**Setup:**
1. Push the workflow file to your GitHub repository
2. The workflow will automatically run every 5 minutes
3. MongoDB credentials are read from `IoS_logins.py` (or set as GitHub Secrets if preferred)

**Manual Trigger:**
- Go to Actions tab in GitHub
- Select "Sync NEM Prices to MongoDB"
- Click "Run workflow"

**Note:** For private repositories, GitHub Actions has limited free minutes per month. For frequent runs (every 5 minutes), consider using the local scheduler option below.

### Option 2: Python Scheduler (Local)

For local automation, use the `auto_sync.py` script that runs continuously on your machine.

**Setup:**
1. Install the `schedule` library:
   ```bash
   pip install -r power_price/requirements.txt
   ```

2. Run the scheduler:
   ```bash
   python power_price/auto_sync.py
   ```

3. For Windows background service (no console window):
   ```bash
   pythonw power_price/auto_sync.py
   ```

**Features:**
- Runs sync every 5 minutes automatically
- Logs to `power_price/auto_sync.log`
- Runs initial sync immediately on startup
- Graceful shutdown with Ctrl+C

**Windows Task Scheduler Setup:**
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "When the computer starts" or "Daily"
4. Action: Start a program
5. Program: `pythonw.exe`
6. Arguments: `C:\Projects\plug\power_price\auto_sync.py`
7. Start in: `C:\Projects\plug`
8. Check "Run whether user is logged on or not"

**Note:** The local scheduler requires your machine to be running. For 24/7 operation, consider using GitHub Actions or a cloud server.

## Data Sources

The script fetches from three NEMweb sources:
1. **Dispatch Reports** (`DISPATCH_REPORTS_URL`): Historical settlement prices (collected continuously)
2. **P5 Reports** (`P5_REPORTS_URL`): 5-minute predispatch forecasts (last 2 hours only)
3. **Predispatch Reports** (`PREDISPATCH_REPORTS_URL`): 30-minute predispatch forecasts (last 2 hours only)

**Collection Limits:**
- Historical dispatch: All available data (no limit)
- 5-minute forecast: Only next 2 hours ahead
- 30-minute forecast: Only next 2 hours ahead

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
- Cleanup statistics (forecast data removed)
- Error summary

## Notes

- The script uses the existing `fetch_prices.py` module for data fetching
- Data is cached locally before syncing to MongoDB
- Timezone handling uses `Australia/Sydney` (AEST/AEDT)
- File timestamps are extracted from NEMweb filenames
- Forecast data cleanup runs automatically after each sync
- Historical dispatch data older than 48 hours is automatically deleted
- Documents between 2-48 hours old have forecast fields removed but keep historical_price

