@echo off
echo ====================================================
echo USB Network Share V3 - Professional Edition Setup
echo ====================================================
echo.

echo Installing Python dependencies...
pip install -r requirements_v3.txt

echo.
echo ====================================================
echo Installation Complete!
echo ====================================================
echo.
echo What's New in V3:
echo   ✓ Automatic server discovery (mDNS/Bonjour)
echo   ✓ Configuration persistence (never re-enter settings!)
echo   ✓ Optional TLS encryption for security
echo   ✓ Priority command queue (emergency stops first!)
echo   ✓ Enhanced performance metrics
echo   ✓ All V2 features included (auto-reconnect, heartbeat, etc.)
echo.
echo IMPORTANT: You still need com0com on the CLIENT computer!
echo Download from: https://sourceforge.net/projects/com0com/
echo.
echo Quick Start:
echo   1. Read QUICK_START_V3.md for setup instructions
echo   2. Server: python usb_network_share_server_v3.py
echo   3. Client: python usb_network_share_client_v3.py
echo.
echo Documentation:
echo   - QUICK_START_V3.md     - Get started in 5 minutes
echo   - README_V3.md          - Complete user manual
echo   - CHANGELOG_V3.md       - What changed from V2
echo   - IMPLEMENTATION_COMPLETE.md - Feature summary
echo.
echo Configuration files will be saved to:
echo   Windows: %%APPDATA%%\USBNetworkShare\
echo   Settings persist across restarts automatically!
echo.
pause
