#!/bin/bash

echo "🚀 Starting TidyBot with Docker..."
echo "================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Build the Docker image
echo "📦 Building Docker image..."
docker-compose build

# Start the services
echo "🎯 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 5

# Check health
if curl -f http://localhost:11007/health > /dev/null 2>&1; then
    echo "✅ TidyBot is running!"
    echo ""
    echo "🌐 Services:"
    echo "   • API Server: http://localhost:11007"
    echo "   • API Docs: http://localhost:11007/docs"
    echo "   • Web Frontend: http://localhost:80"
    echo ""
    echo "📊 Container status:"
    docker-compose ps
else
    echo "⚠️ TidyBot failed to start. Check logs:"
    echo "   docker-compose logs ai-service"
fi

echo "================================"
echo "To stop: ./scripts/docker-stop.sh"
echo "To view logs: docker-compose logs -f"