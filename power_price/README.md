# NEMweb Power Price Data Fetcher

Fetches and caches electricity price data from NEMweb for the VIC1 (Victoria) region.

## Overview

This module downloads predispatch price forecasts from the Australian Energy Market Operator (AEMO) NEMweb portal and caches them locally as JSON files. The data is automatically adjusted from AEST (Australian Eastern Standard Time) to AEDT (Australian Eastern Daylight Time) to match the current timezone.

## Features

- **Automatic File Discovery**: Finds the latest predispatch IRSR file by parsing the NEMweb directory listing
- **Timezone Conversion**: Automatically converts AEST market data to AEDT (adds 1 hour)
- **Smart Caching**: Caches data by date (YYYYMMDD) to avoid redundant downloads
- **VIC1 Region Filtering**: Extracts only Victoria region price data
- **12-Hour Forecast**: Extracts the next 12 hours of predispatch prices
- **JSON Output**: Saves data in a structured JSON format for easy consumption

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Required packages:
- `requests` - HTTP downloads
- `beautifulsoup4` - HTML parsing
- `pytz` - Timezone handling

## Usage

### Basic Usage

Run the script to fetch the latest predispatch prices:

```bash
python power_price/fetch_prices.py
```

### Force Refresh

To force a refresh even if cached data exists:

```bash
python power_price/fetch_prices.py --refresh
# or
python power_price/fetch_prices.py -r
```

### Programmatic Usage

```python
from power_price.fetch_prices import fetch_predispatch_prices

# Fetch latest predispatch prices
data = fetch_predispatch_prices(region='VIC1', hours_ahead=12)

if data:
    print(f"Fetched {len(data['prices'])} price points")
    for price_point in data['prices']:
        print(f"{price_point['timestamp']}: ${price_point['price']}/MWh")
```

## Output Format

The script generates JSON files in the `power_price/` directory with the following structure:

**File naming**: `predispatch_vic1_YYYYMMDD.json`

**JSON structure**:
```json
{
  "region": "VIC1",
  "data_date": "20251116",
  "timezone": "AEDT",
  "source_file": "PUBLIC_PREDISPATCH_IRSR_202511160830_0000000489556762.zip",
  "fetched_at": "2025-11-16T20:30:00+11:00",
  "hours_ahead": 12,
  "prices": [
    {
      "timestamp": "2025-11-16T20:30:00",
      "price": 45.23
    },
    {
      "timestamp": "2025-11-16T21:00:00",
      "price": 48.15
    }
  ]
}
```

## Data Source

- **URL**: https://nemweb.com.au/Reports/Current/Predispatch_IRSR/
- **Update Frequency**: Files are updated every 30 minutes
- **Data Type**: Predispatch price forecasts (12 hours ahead)
- **Region**: VIC1 (Victoria)

## Timezone Handling

The NEMweb market data uses AEST (Australian Eastern Standard Time, UTC+10). However, during daylight saving time, the current timezone is AEDT (UTC+11). The script automatically:

1. Detects the current timezone (AEDT during DST)
2. Adds 1 hour to all market timestamps to convert from AEST to AEDT
3. Filters data to show only the next 12 hours from the current time

## Caching

The script implements smart caching:

- Files are cached by date (YYYYMMDD) in the filename
- If a cached file exists for today's date, it will be used unless `--refresh` is specified
- Cached files are stored in the `power_price/` directory
- Old cached files are not automatically deleted (you may want to clean them up periodically)

## Error Handling

The script handles various error conditions gracefully:

- Network timeouts and connection errors
- Missing or malformed CSV files
- Unrecognized file formats
- Missing required columns in CSV data

Errors are logged to the console with `[ERROR]` or `[WARNING]` prefixes.

## Troubleshooting

### No files found
- Check your internet connection
- Verify the NEMweb URL is accessible: https://nemweb.com.au/Reports/Current/Predispatch_IRSR/
- The directory listing format may have changed

### No price data extracted
- The CSV file format may have changed
- Check that the file contains VIC1 region data
- Verify the column names match expected patterns (REGIONID, INTERVAL_DATETIME, RRP)

### Timezone issues
- Ensure `pytz` is installed and up to date
- The script uses `Australia/Sydney` timezone which automatically handles AEST/AEDT

## Future Enhancements

- [ ] Add support for fetching historical/current dispatch prices
- [ ] Support for other regions (NSW1, QLD1, SA1, TAS1)
- [ ] Automatic cleanup of old cached files
- [ ] Integration with the main server.py for real-time price updates
- [ ] Price alerts and notifications

## License

Part of the Smart Home Device Control Suite project.



