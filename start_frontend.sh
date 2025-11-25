#!/bin/bash

echo "Starting Frontend Development Server..."
echo ""

cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

echo ""
echo "Frontend server starting on http://localhost:5173"
echo "Press Ctrl+C to stop"
echo ""

npm run dev















