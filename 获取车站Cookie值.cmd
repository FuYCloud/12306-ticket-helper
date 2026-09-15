@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   12306 车站 Cookie 值获取工具
echo ========================================
echo.
python tools\get_station_cookie.py