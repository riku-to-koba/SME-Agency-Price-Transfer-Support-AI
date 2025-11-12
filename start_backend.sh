#!/bin/bash

echo "Starting Backend Server..."
echo ""

# 仮想環境をアクティベート
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
    pip install -r api/requirements.txt
fi

echo ""
echo "Backend server starting on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

python api/main.py

