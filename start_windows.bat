@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo [Flash Ogiri] Installing / checking dependencies...
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo Python was not found, or package installation failed.
  echo Install Python from https://www.python.org/downloads/
  pause
  exit /b 1
)
echo.
echo Ready! Open http://localhost:8080 in your browser.
echo To play on other devices on the same Wi-Fi, use this PC's local IP and port 8080.
echo Press Ctrl+C to stop the server.
py -3 server.py
pause
