#!/bin/bash

echo "🚀 Starting TidyBot Server..."
echo "================================"

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Navigate to the project root then to AI service directory
cd "$SCRIPT_DIR/../tidybot/ai_service"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt

# Check if Tesseract is installed
if ! command -v tesseract &> /dev/null; then
    echo "⚠️  Tesseract OCR not found. Please install it:"
    echo "   macOS: brew install tesseract"
    echo "   Linux: sudo apt-get install tesseract-ocr"
fi

# Download NLTK data if needed
python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True)" 2>/dev/null

# Start the server
echo "✅ Starting server on http://localhost:11007"
echo "📖 API docs available at http://localhost:11007/docs"
echo "Press Ctrl+C to stop the server"
echo "================================"

uvicorn app.main:app --reload --host 0.0.0.0 --port 11007