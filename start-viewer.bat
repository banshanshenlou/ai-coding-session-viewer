@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3 并将 python 加入 PATH。
    echo [提示] 安装完成后重新运行本脚本。
    goto :end
)

python -m pip --version >nul 2>nul
if errorlevel 1 (
    echo [错误] 已检测到 Python，但当前环境不可用 pip。
    echo [提示] 请先执行 python -m ensurepip 或重新安装带 pip 的 Python。
    goto :end
)

echo Installing dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络或 Python 环境后重试。
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
