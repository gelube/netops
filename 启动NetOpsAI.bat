@echo off
cd /d "%~dp0"
echo 启动 NetOps AI Web 服务...
echo.
py web\app_local.py
pause