@echo off
echo Starting Backend Server...
echo.

REM 仮想環境をアクティベート
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Creating...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
    pip install -r api/requirements.txt
)

echo.
echo Backend server starting on http://localhost:8000
echo Press Ctrl+C to stop
echo.

python api/main.py

pause


