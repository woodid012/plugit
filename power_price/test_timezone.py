"""
Test script to verify timezone handling for NEMweb timestamps
"""

import sys
from pathlib import Path
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_prices import AEST_FIXED, AEST

def test_timezone_handling():
    """Test that market timestamps are stored in AEST (UTC+10)"""
    
    print("=" * 80)
    print("Testing Timezone Handling for NEMweb Market Timestamps")
    print("=" * 80)
    print()
    
    # Test timestamp from NEMweb (market time - always AEST)
    market_time_str = "2025/11/19 14:05:00"
    
    # Parse as naive datetime
    dt = datetime.strptime(market_time_str, '%Y/%m/%d %H:%M:%S')
    print(f"1. Parsed naive datetime: {dt}")
    print()
    
    # Localize to AEST_FIXED (UTC+10) - this is what we should use for market timestamps
    dt_aest = AEST_FIXED.localize(dt)
    print(f"2. Localized to AEST_FIXED (UTC+10): {dt_aest}")
    print(f"   ISO format: {dt_aest.isoformat()}")
    print(f"   UTC offset: {dt_aest.utcoffset()}")
    print()
    
    # Compare with AEST (which changes with DST)
    dt_aest_dst = AEST.localize(dt)
    print(f"3. Localized to AEST (Australia/Sydney - changes with DST): {dt_aest_dst}")
    print(f"   ISO format: {dt_aest_dst.isoformat()}")
    print(f"   UTC offset: {dt_aest_dst.utcoffset()}")
    print()
    
    # Check if we're currently in DST
    now_sydney = datetime.now(AEST)
    is_dst = now_sydney.dst() != timedelta(0)
    print(f"4. Current time in Australia/Sydney: {now_sydney}")
    print(f"   Currently in DST (AEDT): {is_dst}")
    print(f"   Current UTC offset: {now_sydney.utcoffset()}")
    print()
    
    # Show the difference
    if dt_aest != dt_aest_dst:
        print("WARNING: AEST_FIXED and AEST produce different results!")
        print(f"   Difference: {dt_aest_dst - dt_aest}")
        print()
        print("SOLUTION: Use AEST_FIXED for market timestamps to ensure")
        print("   they are always stored as UTC+10 (AEST) regardless of DST")
    else:
        print("AEST_FIXED and AEST produce the same result (not in DST)")
    
    print()
    print("=" * 80)
    print("Expected MongoDB timestamp format:")
    print(f"  {dt_aest.isoformat()}")
    print("=" * 80)

if __name__ == '__main__':
    from datetime import timedelta
    test_timezone_handling()

