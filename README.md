# TidyBot - AI-Powered File Organization

TidyBot uses AI to automatically analyze, rename, and organize your files based on their content.

## Features

- **Smart File Analysis**: OCR, object detection, document parsing
- **Intelligent Naming**: AI-generated names based on content
- **Batch Processing**: Handle multiple files efficiently
- **Search & Index**: Find files by content, not just names
- **CLI Interface**: Easy command-line usage

## Quick Start

### Install & Run
```bash
# Install dependencies
./install_cli.sh

# Start server
tidybot-server

# Use CLI (in another terminal)
tidybot recommend ~/Downloads
tidybot search "invoice"
tidybot index ~/Documents
```

### Manual Installation
```bash
# Install package
pip install -e .

# Start server
python3 main.py

# Use CLI
python3 tidybot_cli_v2.py recommend ~/Downloads
```

## CLI Commands

```bash
# File organization
tidybot recommend ~/Downloads              # Show rename suggestions
tidybot auto ~/Documents --dry-run         # Preview auto-rename
tidybot reorganize ~/Desktop               # Reorganize folder

# Search functionality  
tidybot search "amazon invoice"            # Search files
tidybot index ~/Documents                  # Index directory
tidybot stats                              # Show statistics
```

## API

- **Docs**: http://localhost:11007/docs
- **Health**: http://localhost:11007/health

Key endpoints:
- `POST /api/v1/files/process` - Process single file
- `POST /api/v1/batch/process` - Batch processing
- `POST /api/v1/search/query` - Search files

## Requirements

- Python 3.8+
- Tesseract OCR
- 4GB+ RAM (for AI models)

## License

GPL-3.0 - see LICENSE file