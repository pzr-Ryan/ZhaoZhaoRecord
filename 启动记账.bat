@echo off
chcp 65001 >nul
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo 启动失败：请确认已安装 Python 3.9 或更高版本，并已加入 PATH。
    pause
)
