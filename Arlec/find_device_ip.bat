@echo off
echo ====================================================================
echo Network Device Scanner - Find Your Arlec Plug
echo ====================================================================
echo.
echo Scanning network for all connected devices...
echo Look for devices with manufacturers like:
echo - Espressif (common in smart plugs)
echo - Tuya
echo - Your device name
echo.
echo ====================================================================
echo.

arp -a

echo.
echo ====================================================================
echo TIP: Look at your router's admin panel for more details
echo Common router addresses: 192.168.1.1, 192.168.0.1, 192.168.86.1
echo ====================================================================
pause
