# Standalone Components

This directory contains standalone components that are not integrated into the main `server.py`. These can be run independently for specific use cases.

## Power Price Components

- **power_price_api_server.py** - Standalone Flask API server for NEMweb price data
- **power_price_dashboard.html** - Standalone HTML dashboard for viewing price data
- **create_chart.py** - Chart generation utility for price data
- **timeseries_with_prices.py** - Timeseries visualization utility

## Usage

### Standalone Power Price API Server

```bash
python _standalone/power_price_api_server.py
```

Then access the dashboard at `http://localhost:5001` (or the port shown).

### Standalone Dashboard

Simply open `_standalone/power_price_dashboard.html` in your browser. It will load data from `power_price/nem_price_cache.json`.

### Chart Generation

```bash
python _standalone/create_chart.py
python _standalone/timeseries_with_prices.py
```

## Note

The main integrated system uses `server.py` which includes power price functionality. These standalone components are provided for:
- Independent testing
- Separate deployment
- Custom use cases
- Development and debugging

