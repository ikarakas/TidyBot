# TidyBot Search, Indexing & Offline Capabilities

## Overview

This document describes the newly implemented search, indexing, and offline capabilities for TidyBot. These features enable comprehensive file management with intelligent search, real-time indexing, and robust offline functionality.

## Features Implemented

### 1. File Indexing Service (`indexing_service.py`)

#### Capabilities:
- **Directory Indexing**: Recursively index entire directories
- **Real-time Monitoring**: Watch directories for changes using file system events
- **Smart Caching**: Avoid re-indexing unchanged files
- **Background Processing**: Queue-based asynchronous indexing
- **Multi-format Support**: Index documents, images, code files, and more

#### Key Functions:
```python
# Index a directory
await indexing_service.index_directory(
    directory_path=Path("/Users/docs"),
    recursive=True,
    monitor=True  # Enable real-time monitoring
)

# Index a single file
await indexing_service.index_file(Path("/Users/docs/report.pdf"))

# Get index statistics
stats = await indexing_service.get_index_stats()
```

### 2. Search Engine (`search_engine.py`)

#### Search Types:
1. **Natural Language Search**: Understands queries like "find invoices from last month"
2. **Semantic Search**: Uses AI embeddings for meaning-based search
3. **Exact Search**: Find exact phrases
4. **Fuzzy Search**: Tolerates typos and variations
5. **Regex Search**: Pattern-based searching

#### Natural Language Understanding:
- Date parsing: "yesterday", "last week", "since January"
- Size constraints: "larger than 5MB", "smaller than 100KB"
- File type detection: "images", "documents", "spreadsheets"
- Category inference: "invoices", "contracts", "reports"

#### Example Queries:
```python
# Natural language examples
"find all presentations about marketing from last quarter"
"images larger than 5mb taken yesterday"
"documents containing budget information"
"contracts with TechCorp signed this year"
"pdfs created last week"
```

### 3. Offline Manager (`offline_manager.py`)

#### Capabilities:
- **Local Caching**: SQLite-based persistent cache
- **Search Result Caching**: Store and retrieve search results offline
- **Operation Queue**: Queue changes when offline, sync when online
- **Conflict Resolution**: Handle sync conflicts intelligently
- **Auto-sync**: Background synchronization when connection restored

#### Cache Management:
```python
# Cache file for offline access
await offline_manager.cache.cache_file(
    file_path="/path/to/file",
    content="file content",
    metadata={...},
    analysis_result={...}
)

# Queue offline operation
await offline_manager.queue_operation(
    operation_type=OperationType.UPDATE,
    file_path="/path/to/file",
    data={"new_content": "..."}
)

# Force sync when online
await offline_manager.sync_now()
```

## API Endpoints

### Search Endpoints

#### `GET /api/v1/search/search`
Search indexed files with natural language queries.

**Parameters:**
- `q`: Search query (required)
- `search_type`: Type of search (natural_language, semantic, exact, fuzzy, regex)
- `limit`: Maximum results (default: 50)
- `include_content`: Include content preview
- `file_types`: Filter by file extensions
- `categories`: Filter by categories
- `date_from`/`date_to`: Date range filters
- `min_size`/`max_size`: Size filters

**Example:**
```bash
curl "http://localhost:8000/api/v1/search/search?q=invoices%20from%20january&search_type=natural_language"
```

#### `POST /api/v1/search/index/directory`
Index all files in a directory.

**Body:**
```json
{
  "path": "/Users/Documents",
  "recursive": true,
  "monitor": true
}
```

#### `POST /api/v1/search/index/file`
Index a single file.

**Body:**
```json
{
  "path": "/Users/Documents/report.pdf"
}
```

#### `GET /api/v1/search/index/stats`
Get indexing and cache statistics.

#### `POST /api/v1/search/offline/sync`
Manually trigger offline sync.

#### `POST /api/v1/search/offline/status`
Set online/offline mode.

## Installation

1. Install required dependencies:
```bash
cd tidybot/ai_service
pip install -r requirements_search.txt
```

2. Download spaCy language model:
```bash
python -m spacy download en_core_web_sm
```

3. Initialize the database:
```bash
python -c "from app.database import init_db; import asyncio; asyncio.run(init_db())"
```

## Usage Examples

### Python Client Example

```python
import asyncio
from pathlib import Path
from services.indexing_service import IndexingService
from services.search_engine import SearchEngine, SearchQuery, SearchType

async def example():
    # Initialize services
    indexing = IndexingService()
    search = SearchEngine()

    # Index a directory
    await indexing.index_directory(
        Path("/Users/Documents"),
        recursive=True,
        monitor=True
    )

    # Search with natural language
    query = SearchQuery(
        query_text="find all invoices from last month",
        search_type=SearchType.NATURAL_LANGUAGE,
        limit=10
    )

    results = await search.search(query)

    for result in results:
        print(f"{result.file_name} - Score: {result.score}")

asyncio.run(example())
```

### REST API Example

```python
import requests

# Index a directory
response = requests.post(
    "http://localhost:8000/api/v1/search/index/directory",
    params={
        "path": "/Users/Documents",
        "recursive": True,
        "monitor": True
    }
)

# Search files
response = requests.get(
    "http://localhost:8000/api/v1/search/search",
    params={
        "q": "presentations about marketing",
        "search_type": "natural_language",
        "limit": 20
    }
)

results = response.json()
```

## Testing

Run the comprehensive test suite:

```bash
python test_search_indexing.py
```

This will test:
- File indexing
- All search types
- Natural language parsing
- Offline caching
- Operation queuing
- Cache cleanup

## Configuration

### Environment Variables

```bash
# Search index location
TIDYBOT_INDEX_DIR=/path/to/index

# Cache directory
TIDYBOT_CACHE_DIR=/path/to/cache

# Enable semantic search (requires GPU for better performance)
TIDYBOT_USE_GPU=true

# Offline sync interval (seconds)
TIDYBOT_SYNC_INTERVAL=30

# Maximum cache size (MB)
TIDYBOT_MAX_CACHE_SIZE=1000
```

### Performance Tuning

1. **Indexing Performance**:
   - Batch size: Adjust batch processing size for large directories
   - Worker threads: Configure number of indexing workers
   - Cache size: Balance memory usage vs. performance

2. **Search Performance**:
   - Use Whoosh index optimization periodically
   - Enable result caching for frequent queries
   - Limit semantic search to top N results

3. **Offline Performance**:
   - Set appropriate cache expiration times
   - Configure sync retry strategies
   - Implement progressive cache cleanup

## Architecture

```
┌─────────────────────────────────────────────┐
│                  TidyBot UI                  │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│              FastAPI Server                  │
│  ┌─────────────────────────────────────┐    │
│  │         Search API Endpoints         │    │
│  └─────────────────────────────────────┘    │
└─────────────────┬───────────────────────────┘
                  │
        ┌─────────┴─────────┬──────────────┐
        │                   │               │
┌───────▼────────┐ ┌────────▼──────┐ ┌─────▼──────┐
│ Indexing       │ │ Search Engine │ │ Offline    │
│ Service        │ │               │ │ Manager    │
│                │ │ • Natural     │ │            │
│ • File Monitor │ │   Language    │ │ • Cache    │
│ • Background   │ │ • Semantic    │ │ • Queue    │
│   Processing   │ │ • Fuzzy       │ │ • Sync     │
└────────────────┘ └───────────────┘ └────────────┘
        │                   │               │
        └─────────┬─────────┴───────────────┘
                  │
         ┌────────▼────────┐
         │                 │
         │  Data Storage   │
         │                 │
         │ • SQLite Cache  │
         │ • Whoosh Index  │
         │ • PostgreSQL DB │
         └─────────────────┘
```

## Limitations & Future Improvements

### Current Limitations:
1. Semantic search requires significant memory for embeddings
2. Real-time monitoring limited to local file systems
3. No distributed indexing for very large datasets
4. Search results not yet integrated with cloud storage

### Planned Improvements:
1. **Elasticsearch Integration**: For enterprise-scale deployments
2. **Distributed Indexing**: Support for multiple indexing workers
3. **Cloud Storage Integration**: Index Google Drive, Dropbox, etc.
4. **Advanced NLP**: Better query understanding and intent detection
5. **Search Analytics**: Track popular queries and optimize accordingly
6. **Incremental Indexing**: More efficient updates for large files
7. **Custom Analyzers**: Domain-specific text analysis (legal, medical, etc.)

## Troubleshooting

### Common Issues:

1. **"No module named 'spacy'"**
   ```bash
   pip install spacy
   python -m spacy download en_core_web_sm
   ```

2. **"Whoosh index corrupted"**
   ```bash
   rm -rf tidybot_index/
   # Restart service to rebuild index
   ```

3. **"Out of memory during semantic search"**
   - Reduce batch size in search operations
   - Disable semantic search: `search_type="exact"`
   - Use CPU instead of GPU for smaller memory footprint

4. **"File monitoring not working"**
   - Check file system permissions
   - Verify watchdog is installed: `pip install watchdog`
   - Some network drives don't support file system events

## Support

For issues or questions about the search and indexing features, please:
1. Check this documentation
2. Run the test suite to verify installation
3. Review the API endpoint documentation
4. Check application logs for detailed error messages

## License

This implementation is part of the TidyBot project and follows the same license terms.