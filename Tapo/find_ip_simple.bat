@echo off
echo ============================================================
echo Simple Network Device Finder (Windows)
echo ============================================================
echo.
echo This will show all devices on your network.
echo Look for devices with names like "Tapo" or from "TP-Link"
echo.
pause
echo.
echo Scanning network...
echo.
arp -a
echo.
echo ============================================================
echo Look for IP addresses in your local range (192.168.x.x)
echo You can try these IPs in the Tapo control script
echo ============================================================
echo.
pause
