"""
Test script to verify dispatch price parsing fixes
Tests the specific file: PUBLIC_DISPATCH_202511191405_20251119140023_LEGACY.zip
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import fetch_prices
sys.path.insert(0, str(Path(__file__).parent))

from fetch_prices import parse_region_csv, download_and_extract_zip
import tempfile

def test_dispatch_file():
    """Test parsing the specific dispatch file"""
    url = "https://nemweb.com.au/Reports/Current/Dispatch_Reports/PUBLIC_DISPATCH_202511191405_20251119140023_LEGACY.zip"
    
    print("=" * 80)
    print("Testing Dispatch File Parsing")
    print("=" * 80)
    print(f"URL: {url}")
    print()
    
    # Download and extract
    print("[1/3] Downloading and extracting ZIP file...")
    temp_dir = download_and_extract_zip(url)
    
    if not temp_dir:
        print("[ERROR] Failed to download/extract ZIP file")
        return False
    
    try:
        # Find CSV file
        csv_files = list(Path(temp_dir.name).glob("*.CSV"))
        if not csv_files:
            csv_files = list(Path(temp_dir.name).glob("*.csv"))
        
        if not csv_files:
            print("[ERROR] No CSV file found in ZIP")
            return False
        
        csv_path = str(csv_files[0])
        print(f"[OK] Found CSV: {csv_path}")
        print()
        
        # Parse for VIC1
        print("[2/3] Parsing CSV for VIC1 region...")
        # Use hours_back=24 to get all available data (or 0 to disable time filtering)
        prices = parse_region_csv(
            csv_path, 
            region='VIC1', 
            table_name='DREGION',
            hours_back=24,  # Get last 24 hours of data to ensure we capture the data
            hours_ahead=0
        )
        
        print()
        print("[3/3] Results:")
        print("-" * 80)
        
        if prices:
            print(f"[SUCCESS] Found {len(prices)} price points for VIC1")
            print()
            print("Sample prices:")
            for i, price in enumerate(prices[:10]):  # Show first 10
                print(f"  {i+1}. {price['timestamp']}: ${price['price']:.2f} AUD/MWh")
            
            if len(prices) > 10:
                print(f"  ... and {len(prices) - 10} more")
            
            # Check for the specific timestamp mentioned (14:05)
            print()
            print("Checking for 14:05 timestamp...")
            found_1405 = False
            for price in prices:
                if '14:05' in price['timestamp']:
                    print(f"[FOUND] 14:05 price: ${price['price']:.2f} AUD/MWh")
                    found_1405 = True
                    break
            
            if not found_1405:
                print("[WARNING] No 14:05 timestamp found in results")
            
            return True
        else:
            print("[ERROR] No prices extracted for VIC1")
            print()
            print("Debugging: Let's check the raw CSV structure...")
            print()
            
            # Read first 20 lines to see structure
            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [f.readline().strip() for _ in range(20)]
                print("First 20 lines of CSV:")
                for i, line in enumerate(lines, 1):
                    if line:
                        # Truncate long lines
                        display_line = line[:100] + "..." if len(line) > 100 else line
                        print(f"  {i:2d}: {display_line}")
            
            return False
    
    finally:
        # Cleanup
        temp_dir.cleanup()
        print()
        print("[OK] Cleaned up temporary files")

if __name__ == '__main__':
    success = test_dispatch_file()
    sys.exit(0 if success else 1)

