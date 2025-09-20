#!/bin/bash

echo "🛑 Stopping TidyBot Server..."
echo "================================"

# Kill any running uvicorn processes
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo "📍 Found running TidyBot server processes"
    pkill -f "uvicorn app.main:app"
    echo "✅ Server processes terminated"
else
    echo "ℹ️  No TidyBot server processes found"
fi

# Check if port is still in use
if lsof -i :11007 | grep -q LISTEN; then
    echo "⚠️  Port 11007 is still in use"
    echo "   Forcing closure..."
    lsof -ti :11007 | xargs kill -9 2>/dev/null
    echo "✅ Port 11007 freed"
else
    echo "✅ Port 11007 is free"
fi

echo "================================"
echo "✅ TidyBot Server stopped"
echo "================================"