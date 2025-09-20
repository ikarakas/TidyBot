# TidyBot Project Structure

## 📁 Organized Folder Structure

```
TidyBot/
├── main.py                     # Main Python entry point
├── setup.py                    # Python package setup
├── Dockerfile                  # Docker container definition
├── docker-compose.yml          # Docker services orchestration
├── .dockerignore              # Docker build exclusions
├── README.md                  # Project documentation
│
├── scripts/                   # Bash scripts
│   ├── run_server.sh         # Start local development server
│   ├── stop_server.sh        # Stop local server
│   ├── docker-start.sh       # Start Docker deployment
│   └── docker-stop.sh        # Stop Docker deployment
│
├── tests/                     # Test files
│   ├── test_complete_functionality.py
│   ├── test_integration.py
│   ├── test_language_detection.py
│   ├── test_load.py
│   ├── test_regression.py
│   ├── test_tidybot.py
│   └── test_verification.py
│
└── tidybot/                   # Main application
    ├── ai_service/           # Backend API service
    │   ├── app/
    │   │   ├── main.py      # FastAPI app
    │   │   ├── api/         # API endpoints
    │   │   ├── database.py  # Database config
    │   │   └── utils/       # Utilities
    │   │
    │   ├── services/        # Core services
    │   │   ├── file_processor.py
    │   │   ├── naming_engine.py
    │   │   ├── organization_engine.py
    │   │   ├── language_detector.py
    │   │   ├── image_analyzer.py
    │   │   ├── document_analyzer.py
    │   │   └── search_engine.py
    │   │
    │   └── requirements.txt
    │
    └── frontend/            # Frontend applications
        └── TidyBot/        # Swift macOS app
            └── TidyBot/
                ├── Views/
                ├── Services/
                └── ViewModels/
```

## 🚀 Quick Start

### Local Development
```bash
# Start server
./scripts/run_server.sh

# Stop server
./scripts/stop_server.sh

# Or use Python directly
python main.py
```

### Docker Deployment
```bash
# Start with Docker
./scripts/docker-start.sh

# Stop Docker
./scripts/docker-stop.sh

# View logs
docker-compose logs -f
```

### Run Tests
```bash
# Run all tests
python -m pytest tests/

# Run specific test
python tests/test_complete_functionality.py
```

## 🔌 Services

- **API Server**: http://localhost:11007
- **API Documentation**: http://localhost:11007/docs
- **Web Frontend**: http://localhost:80 (when using Docker)
- **Redis Cache**: http://localhost:6379 (when using Docker)

## 📦 Docker Services

The `docker-compose.yml` includes:
- **ai-service**: Main TidyBot API server
- **redis**: Caching and queue management
- **nginx**: Reverse proxy and static file serving

## 🛠️ Environment Variables

- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection for caching
- `DEBUG`: Debug mode (True/False)
- `LOG_LEVEL`: Logging level (INFO/DEBUG/ERROR)
- `USE_GPU`: Enable GPU acceleration (True/False)
- `TESSERACT_PATH`: Path to Tesseract OCR
- `UPLOAD_DIR`: Directory for uploads
- `BACKUP_DIR`: Directory for backups

## 🧪 Testing

All test files are organized in the `tests/` folder:
- Unit tests
- Integration tests
- Load tests
- Regression tests
- Verification tests

## 🐳 Docker Commands

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f ai-service

# Stop and remove containers
docker-compose down

# Stop and remove everything including volumes
docker-compose down -v
```