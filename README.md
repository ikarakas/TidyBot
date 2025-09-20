# TidyBot - AI-Powered File Management Application

TidyBot is an intelligent file organization and renaming system that uses AI to automatically analyze, rename, and organize your files based on their content.

## Features

### Core Capabilities
- **Intelligent File Analysis**: Analyzes images, documents, and other files using AI
- **Smart Naming Engine**: Generates meaningful names based on file content
- **Batch Processing**: Process multiple files simultaneously
- **Automatic Organization**: Sorts files into appropriate folders
- **Preset Management**: Save and reuse naming conventions

### File Analysis
- **Image Analysis**:
  - OCR text extraction
  - Object detection
  - Scene recognition
  - EXIF data extraction
  - Caption generation

- **Document Analysis**:
  - PDF, Word, Excel, PowerPoint support
  - Keyword extraction
  - Date detection
  - Summary generation
  - Metadata extraction

## Architecture

```
TidyBot/
├── ai_service/      # Python FastAPI service for AI processing
├── backend/         # Go backend for file operations (planned)
├── frontend/        # Swift/Web frontend (planned)
└── shared/          # Shared utilities
```

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- Tesseract OCR

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tidybot.git
cd tidybot
```

2. Install dependencies:
```bash
cd tidybot/ai_service
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run with Docker:
```bash
docker-compose up -d
```

Or run locally:
```bash
cd tidybot/ai_service
uvicorn app.main:app --reload
```

## API Documentation

Once running, access the interactive API documentation at:
- Swagger UI: `http://localhost:11007/docs`
- ReDoc: `http://localhost:11007/redoc`

### Key Endpoints

#### File Processing
- `POST /api/v1/files/process` - Process a single file
- `POST /api/v1/files/rename` - Generate name suggestions

#### Batch Processing
- `POST /api/v1/batch/process` - Process multiple files
- `GET /api/v1/batch/status/{job_id}` - Check job status

#### Analysis
- `POST /api/v1/analysis/image` - Analyze image files
- `POST /api/v1/analysis/document` - Analyze documents

#### Presets
- `GET /api/v1/presets/` - List all presets
- `POST /api/v1/presets/` - Create new preset

## Usage Examples

### Process a Single File
```python
import requests

with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:11007/api/v1/files/process',
        files={'file': f}
    )
    result = response.json()
    print(f"Suggested name: {result['suggested_name']}")
    print(f"Confidence: {result['confidence_score']}")
```

### Batch Processing
```python
files = [
    ('files', open('file1.jpg', 'rb')),
    ('files', open('file2.pdf', 'rb')),
    ('files', open('file3.docx', 'rb'))
]

response = requests.post(
    'http://localhost:11007/api/v1/batch/process',
    files=files
)
job_id = response.json()['job_id']

# Check status
status_response = requests.get(
    f'http://localhost:11007/api/v1/batch/status/{job_id}'
)
print(status_response.json())
```

## Configuration

Key configuration options in `.env`:

```env
# AI Models
USE_GPU=False
MODEL_CACHE_DIR=./models

# OCR
TESSERACT_PATH=/usr/bin/tesseract
OCR_LANGUAGES=eng,fra,spa,deu

# File Processing
MAX_FILE_SIZE_MB=100
ALLOWED_EXTENSIONS=jpg,png,pdf,docx,xlsx

# Performance
BATCH_SIZE=32
MAX_WORKERS=4
```

## Development

### Running Tests
```bash
cd tidybot/ai_service
pytest tests/
```

### Code Quality
```bash
# Format code
black .

# Lint
flake8 .

# Type checking
mypy .
```

## Roadmap

- [ ] Go backend for file system operations
- [ ] Swift desktop application
- [ ] Web interface
- [ ] Mobile companion app
- [ ] Cloud storage integration
- [ ] Team collaboration features
- [ ] Advanced ML models for better analysis

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT License - see LICENSE file for details

## Support

For issues and questions, please use the GitHub issue tracker.