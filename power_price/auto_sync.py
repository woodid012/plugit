"""
Automated NEM Price Sync Scheduler
Runs mongodb_sync.py every 5 minutes to keep MongoDB updated with latest price data.

Usage:
    python power_price/auto_sync.py
    
    Or run as a background service on Windows:
    pythonw power_price/auto_sync.py
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import pytz

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import schedule
except ImportError:
    print("[ERROR] 'schedule' library not found. Install it with:")
    print("  pip install schedule")
    sys.exit(1)

try:
    from power_price.mongodb_sync import sync_to_mongodb, sync_historical_only
except ImportError:
    try:
        from mongodb_sync import sync_to_mongodb, sync_historical_only
    except ImportError:
        print("[ERROR] Could not import mongodb_sync module")
        sys.exit(1)

AEST = pytz.timezone('Australia/Sydney')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('power_price/auto_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_sync():
    """Run the MongoDB sync (with forecasts) and log results"""
    logger.info("=" * 80)
    logger.info("Starting scheduled sync (with forecasts)...")
    logger.info(f"Time: {datetime.now(AEST).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 80)
    
    try:
        success = sync_to_mongodb(force_refresh=False)
        if success:
            logger.info("Sync completed successfully")
        else:
            logger.warning("Sync completed with errors (check logs above)")
    except Exception as e:
        logger.error(f"Sync failed with exception: {e}", exc_info=True)
    
    logger.info("=" * 80)
    logger.info("")


def run_historical_sync():
    """Run historical-only sync (last 1 hour = 12 data points) and log results"""
    logger.info("=" * 80)
    logger.info("Starting historical-only sync (last 1 hour)...")
    logger.info(f"Time: {datetime.now(AEST).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 80)
    
    try:
        success = sync_historical_only(hours_back=1, force_refresh=False)
        if success:
            logger.info("Historical sync completed successfully")
        else:
            logger.warning("Historical sync completed with errors (check logs above)")
    except Exception as e:
        logger.error(f"Historical sync failed with exception: {e}", exc_info=True)
    
    logger.info("=" * 80)
    logger.info("")


def main():
    """Main scheduler loop"""
    logger.info("=" * 80)
    logger.info("NEM Price Auto-Sync Scheduler Started")
    logger.info("=" * 80)
    logger.info(f"Start time: {datetime.now(AEST).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("Schedule: Every 5 minutes (full sync with forecasts)")
    logger.info("Schedule: Every 1 hour (historical-only, last 1 hour = 12 data points)")
    logger.info("Log file: power_price/auto_sync.log")
    logger.info("=" * 80)
    logger.info("")
    
    # Schedule the full sync to run every 5 minutes
    schedule.every(5).minutes.do(run_sync)
    
    # Schedule historical-only sync to run every 1 hour
    schedule.every(1).hours.do(run_historical_sync)
    
    # Run immediately on startup
    logger.info("Running initial full sync...")
    run_sync()
    
    logger.info("Running initial historical sync...")
    run_historical_sync()
    
    # Main loop
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    logger.info("")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)  # Check every second
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 80)
        logger.info("Scheduler stopped by user")
        logger.info(f"Stop time: {datetime.now(AEST).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 80)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

