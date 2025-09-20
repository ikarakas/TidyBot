# TidyBot Docker Image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    libmagic1 \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY tidybot/ai_service/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Copy application code
COPY tidybot/ai_service /app/tidybot/ai_service

# Set Python path
ENV PYTHONPATH=/app/tidybot/ai_service

# Expose port
EXPOSE 11007

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import requests; exit(0 if requests.get('http://localhost:11007/health').status_code == 200 else 1)"

# Run the application
CMD ["uvicorn", "tidybot.ai_service.app.main:app", "--host", "0.0.0.0", "--port", "11007"]