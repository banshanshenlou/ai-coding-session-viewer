@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found. Please install Python 3 and add python to PATH.
    echo [INFO] Run this script again after Python installation is complete.
    goto :end
)

python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was found, but pip is not available in the current environment.
    echo [INFO] Run python -m ensurepip first, or reinstall Python with pip enabled.
    goto :end
)

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check your network or Python environment and retry.
    goto :end
)

set "VIEWER_URL=%OPENCODE_VIEWER_URL%"
if "%VIEWER_URL%"=="" set "VIEWER_URL=http://localhost:8765"

echo.
echo Starting OpenCode Session Viewer...
echo Open %VIEWER_URL% in your browser
echo.

python app.py
:end
pause
