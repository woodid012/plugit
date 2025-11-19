"""
Script to download CSV from NEOmobile website.
Logs in, navigates to the report, and downloads the CSV file.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Credentials
EMAIL = "dean.wooding@zenenergy.com.au"
PASSWORD = "Ch1cken1!?"

# Report URL
REPORT_URL = "https://www.neomobile.com.au/Report/ReportView#f=Prices%5CNEM%20Prices&from=2025-11-19%200:00:00&period=Daily*1&instances=NEM&uuid=bf077855-c3e5-4115-bba7-c9e05c03dab6&view=Chart&autoUpdate=false"

# Output directory
OUTPUT_DIR = Path(__file__).parent
OUTPUT_FILE = OUTPUT_DIR / "neomobile_nem_prices.csv"


def download_csv():
    """Download CSV from NEOmobile website."""
    print("Starting NEOmobile CSV download...")
    print(f"Email: {EMAIL}")
    print(f"Report URL: {REPORT_URL}")
    print(f"Output file: {OUTPUT_FILE}")
    print("-" * 60)
    
    with sync_playwright() as p:
        # Launch browser (headless=False so you can see what's happening)
        print("Launching browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Navigate to login page
            print("Navigating to NEOmobile login page...")
            page.goto("https://www.neomobile.com.au/Account/Login", wait_until="networkidle")
            time.sleep(2)  # Give page time to load
            
            # Fill in login form
            print("Filling in login credentials...")
            page.fill('input[name="Email"]', EMAIL)
            page.fill('input[name="Password"]', PASSWORD)
            
            # Click login button
            print("Clicking login button...")
            page.click('button[type="submit"], input[type="submit"]')
            
            # Wait for navigation after login
            print("Waiting for login to complete...")
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(3)  # Additional wait for any redirects
            
            # Check if we're logged in (look for logout link or user menu)
            current_url = page.url
            print(f"Current URL after login: {current_url}")
            
            # Navigate to the report URL
            print("Navigating to report page...")
            page.goto(REPORT_URL, wait_until="networkidle", timeout=60000)
            time.sleep(5)  # Wait for report to load
            
            # Look for CSV download button/link
            print("Looking for CSV download option...")
            
            # Common selectors for CSV export buttons
            csv_selectors = [
                'a[href*="csv"], a[href*="CSV"]',
                'button:has-text("CSV"), button:has-text("Export")',
                'a:has-text("CSV"), a:has-text("Export")',
                '[data-export="csv"]',
                '.export-csv, .csv-export',
                'button[title*="CSV"], a[title*="CSV"]'
            ]
            
            csv_button = None
            for selector in csv_selectors:
                try:
                    csv_button = page.query_selector(selector)
                    if csv_button:
                        print(f"Found CSV button with selector: {selector}")
                        break
                except:
                    continue
            
            if not csv_button:
                # Try to find any export/download button
                print("CSV button not found with common selectors. Looking for any export/download buttons...")
                all_buttons = page.query_selector_all('button, a')
                for btn in all_buttons:
                    text = btn.inner_text().lower()
                    if 'csv' in text or 'export' in text or 'download' in text:
                        csv_button = btn
                        print(f"Found potential export button: {text}")
                        break
            
            if csv_button:
                # Set up download handler
                print("Setting up download handler...")
                with page.expect_download(timeout=30000) as download_info:
                    csv_button.click()
                    time.sleep(2)
                
                download = download_info.value
                
                # Save the downloaded file
                print(f"Saving downloaded file to: {OUTPUT_FILE}")
                download.save_as(OUTPUT_FILE)
                print(f"✓ CSV file saved successfully to: {OUTPUT_FILE}")
                
            else:
                # Alternative: Try to get CSV via direct URL manipulation or API call
                print("CSV button not found. Attempting alternative methods...")
                
                # Check page content for CSV download links
                page_content = page.content()
                if 'csv' in page_content.lower():
                    print("Found 'csv' in page content. Trying to extract download URL...")
                    # You might need to inspect the page to find the exact download mechanism
                
                # Take a screenshot for debugging
                screenshot_path = OUTPUT_DIR / "neomobile_page_screenshot.png"
                page.screenshot(path=str(screenshot_path))
                print(f"Screenshot saved to: {screenshot_path}")
                print("Please check the screenshot to identify the CSV download button.")
                
                # Try common keyboard shortcuts or right-click menu
                print("Trying alternative: Right-click context menu...")
                # This might not work, but worth trying
                
                raise Exception("Could not find CSV download button. Check screenshot for manual identification.")
            
        except PlaywrightTimeoutError as e:
            print(f"Timeout error: {e}")
            screenshot_path = OUTPUT_DIR / "neomobile_error_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            print(f"Error screenshot saved to: {screenshot_path}")
            raise
            
        except Exception as e:
            print(f"Error occurred: {e}")
            screenshot_path = OUTPUT_DIR / "neomobile_error_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            print(f"Error screenshot saved to: {screenshot_path}")
            raise
            
        finally:
            # Keep browser open for a bit to see the result
            print("\nKeeping browser open for 10 seconds for inspection...")
            time.sleep(10)
            browser.close()
    
    print("\n" + "=" * 60)
    print("Download process completed!")
    print(f"CSV file location: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        download_csv()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Playwright is installed: pip install playwright")
        print("2. Install browser: playwright install chromium")
        print("3. Check your internet connection")
        print("4. Verify login credentials are correct")
        print("5. Check the screenshot files for visual debugging")
        raise


