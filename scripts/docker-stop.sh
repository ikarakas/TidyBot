#!/bin/bash

echo "🛑 Stopping TidyBot Docker containers..."
echo "================================"

# Stop all containers
docker-compose down

# Clean up volumes (optional - uncomment if needed)
# echo "🧹 Cleaning up volumes..."
# docker-compose down -v

echo "✅ TidyBot stopped"
echo "================================"