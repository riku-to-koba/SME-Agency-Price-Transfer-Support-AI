@echo off
echo Starting Frontend Development Server...
echo.

cd frontend

if not exist node_modules (
    echo Installing dependencies...
    call npm install
)

echo.
echo Frontend server starting on http://localhost:5173
echo Press Ctrl+C to stop
echo.

call npm run dev

pause


