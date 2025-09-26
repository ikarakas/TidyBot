from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, Body
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from services.search_engine import SearchEngine, SearchQuery, SearchType
from services.indexing_service import IndexingService
from services.offline_manager import OfflineManager, OperationType

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
search_engine = SearchEngine()
indexing_service = IndexingService()
offline_manager = OfflineManager()


@router.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    await indexing_service.start()
    await offline_manager.start()


@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown"""
    await indexing_service.stop()
    await offline_manager.stop()


@router.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    search_type: str = Query("natural_language", description="Search type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_content: bool = Query(False),
    file_types: Optional[str] = Query(None, description="Comma-separated file extensions"),
    categories: Optional[str] = Query(None, description="Comma-separated categories"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    min_size: Optional[int] = Query(None, description="Minimum file size in bytes"),
    max_size: Optional[int] = Query(None, description="Maximum file size in bytes"),
    use_cache: bool = Query(True),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Execute a search query across indexed files.

    Search types:
    - natural_language: Parse and understand natural language queries
    - semantic: Use AI embeddings for semantic similarity
    - exact: Exact phrase matching
    - fuzzy: Fuzzy matching with edit distance
    - regex: Regular expression search
    """
    try:
        # Check cache if offline
        if use_cache and not offline_manager.is_online:
            cached_results = await offline_manager.cache.get_cached_search(q)
            if cached_results:
                return {
                    'query': q,
                    'results': cached_results,
                    'total': len(cached_results),
                    'cached': True,
                    'offline_mode': True
                }

        # Parse search type
        try:
            search_type_enum = SearchType(search_type)
        except ValueError:
            search_type_enum = SearchType.NATURAL_LANGUAGE

        # Build search query
        filters = {}
        if file_types:
            filters['file_types'] = file_types.split(',')
        if categories:
            filters['categories'] = categories.split(',')

        date_range = None
        if date_from and date_to:
            date_range = (date_from, date_to)

        query_obj = SearchQuery(
            query_text=q,
            search_type=search_type_enum,
            filters=filters,
            limit=limit,
            offset=offset,
            include_content=include_content,
            date_range=date_range,
            file_types=filters.get('file_types'),
            categories=filters.get('categories'),
            min_size=min_size,
            max_size=max_size
        )

        # Execute search
        results = await search_engine.search(query_obj, db)

        # Format results
        formatted_results = [
            {
                'file_path': r.file_path,
                'file_name': r.file_name,
                'score': r.score,
                'highlights': r.highlights,
                'category': r.category,
                'tags': r.tags,
                'file_size': r.file_size,
                'modified_at': r.modified_at.isoformat(),
                'content_preview': r.content_preview
            }
            for r in results
        ]

        # Cache results if online
        if use_cache and offline_manager.is_online:
            await offline_manager.cache.cache_search_results(q, formatted_results)

        return {
            'query': q,
            'search_type': search_type,
            'results': formatted_results,
            'total': len(formatted_results),
            'limit': limit,
            'offset': offset,
            'cached': False
        }

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def search_query(
    request: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """POST endpoint for search with JSON body support"""
    query = request.get('query', '')
    search_type = request.get('search_type', 'natural')

    # Map search type to backend
    if search_type == 'natural':
        search_type = 'natural_language'

    # Direct implementation to avoid Query object issue
    try:
        search_type_enum = SearchType(search_type)
    except ValueError:
        search_type_enum = SearchType.NATURAL_LANGUAGE

    query_obj = SearchQuery(
        query_text=query,
        search_type=search_type_enum,
        filters={},
        limit=request.get('limit', 50),
        offset=request.get('offset', 0),
        include_content=request.get('content_only', False)
    )

    results = await search_engine.search(query_obj)

    return {
        'query': query,
        'search_type': search_type,
        'results': [
            {
                'file_path': r.file_path,
                'file_name': r.file_name,
                'score': r.score,
                'snippet': r.snippet,
                'file_size': r.file_size,
                'modified_at': r.modified_at.isoformat() if r.modified_at else None,
                'content_preview': r.content_preview
            }
            for r in results
        ],
        'total': len(results),
        'limit': request.get('limit', 50),
        'offset': request.get('offset', 0)
    }


@router.post("/index/directory")
async def index_directory(
    path: str,
    recursive: bool = Query(True),
    monitor: bool = Query(True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Index all files in a directory.

    Args:
        path: Directory path to index
        recursive: Index subdirectories recursively
        monitor: Monitor directory for changes
    """
    try:
        directory_path = Path(path)

        if not directory_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")

        if not directory_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        # Set database session for indexing service
        indexing_service.db_session = db

        # Start indexing in background if directory is large
        file_count = sum(1 for _ in directory_path.rglob('*') if _.is_file())

        if file_count > 100:
            # Large directory, index in background
            background_tasks.add_task(
                indexing_service.index_directory,
                directory_path,
                recursive,
                monitor
            )

            return {
                'status': 'indexing_started',
                'path': str(directory_path),
                'estimated_files': file_count,
                'background': True
            }
        else:
            # Small directory, index immediately
            result = await indexing_service.index_directory(
                directory_path,
                recursive,
                monitor
            )

            # Update search index
            stats = await indexing_service.get_index_stats()

            return {
                'status': 'completed',
                **result,
                'index_stats': stats
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Index directory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/file")
async def index_file(
    path: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Index a single file"""
    try:
        file_path = Path(path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Set database session
        indexing_service.db_session = db

        # Index the file
        result = await indexing_service.index_file(file_path)

        # Update search index if successful
        if result['status'] == 'indexed':
            file_data = result['file']
            await search_engine.add_to_index({
                'path': file_data['path'],
                'name': file_data['name'],
                'content': file_data.get('content', ''),
                'tags': file_data.get('tags', []),
                'category': file_data.get('category', 'general'),
                'size': file_data.get('size', 0),
                'modified': datetime.fromisoformat(file_data['modified_at']),
                'mime_type': file_data.get('mime_type', 'application/octet-stream')
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Index file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/index/file")
async def remove_from_index(
    path: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Remove a file from the index"""
    try:
        # Set database session
        indexing_service.db_session = db

        # Remove from index
        success = await indexing_service.remove_from_index(path)

        if success:
            # Remove from search index
            await search_engine.remove_from_index(path)

            return {"message": "File removed from index successfully"}
        else:
            raise HTTPException(status_code=404, detail="File not found in index")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove from index error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/stats")
async def get_index_stats(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get statistics about the current index"""
    try:
        indexing_service.db_session = db
        stats = await indexing_service.get_index_stats()

        # Add offline stats
        offline_stats = await offline_manager.get_offline_stats()

        return {
            'index': stats,
            'offline': offline_stats,
            'search_engine': {
                'index_path': str(search_engine.index_dir),
                'has_semantic_search': search_engine.sentence_model is not None
            }
        }

    except Exception as e:
        logger.error(f"Get index stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offline/sync")
async def sync_offline_changes(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Sync offline changes with the server"""
    try:
        result = await offline_manager.sync_now()
        return result

    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offline/status")
async def set_offline_status(
    is_online: bool = Query(..., description="Online status")
) -> Dict[str, str]:
    """Set online/offline status"""
    try:
        await offline_manager.set_online_status(is_online)

        return {
            'status': 'online' if is_online else 'offline',
            'message': f"Status set to {'online' if is_online else 'offline'}"
        }

    except Exception as e:
        logger.error(f"Set offline status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache(
    max_age_days: int = Query(30, description="Maximum age of cache entries in days"),
    max_size_mb: int = Query(1000, description="Maximum cache size in MB")
) -> Dict[str, str]:
    """Clear old or oversized cache entries"""
    try:
        await offline_manager.cache.cleanup_cache(max_age_days, max_size_mb)

        return {
            'message': 'Cache cleanup completed successfully'
        }

    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggest")
async def suggest_completions(
    q: str = Query(..., description="Partial query for suggestions"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
) -> List[str]:
    """Get search query suggestions/completions"""
    try:
        # This could be enhanced with actual query history and ML
        suggestions = []

        # Basic keyword suggestions
        keywords = [
            "files from last week",
            "images larger than 5mb",
            "documents about",
            "presentations from",
            "spreadsheets containing",
            "pdfs created in",
            "photos taken on",
            "invoices from",
            "reports about",
            "contracts with"
        ]

        # Filter suggestions based on partial query
        for keyword in keywords:
            if q.lower() in keyword.lower():
                suggestions.append(keyword)

        return suggestions[:limit]

    except Exception as e:
        logger.error(f"Suggest error: {e}")
        return []