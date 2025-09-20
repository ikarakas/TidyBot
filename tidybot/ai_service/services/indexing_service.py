from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from datetime import datetime
import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles
import aiofiles.os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, FileIndex
from .file_processor import FileProcessor
from .document_analyzer import DocumentAnalyzer
from .image_analyzer import ImageAnalyzer

logger = logging.getLogger(__name__)


class IndexStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    UPDATED = "updated"


@dataclass
class IndexedFile:
    path: str
    name: str
    size: int
    mime_type: str
    created_at: datetime
    modified_at: datetime
    indexed_at: datetime
    content_hash: str
    metadata: Dict[str, Any]
    content: Optional[str]
    tags: List[str]
    category: str
    status: IndexStatus
    error: Optional[str] = None

    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['modified_at'] = self.modified_at.isoformat()
        data['indexed_at'] = self.indexed_at.isoformat()
        return data


class FileSystemMonitor(FileSystemEventHandler):
    def __init__(self, indexing_service):
        self.indexing_service = indexing_service
        self.pending_changes = set()
        self.lock = asyncio.Lock()

    def on_created(self, event):
        if not event.is_directory:
            asyncio.create_task(self._handle_file_change(event.src_path, 'created'))

    def on_modified(self, event):
        if not event.is_directory:
            asyncio.create_task(self._handle_file_change(event.src_path, 'modified'))

    def on_deleted(self, event):
        if not event.is_directory:
            asyncio.create_task(self._handle_file_change(event.src_path, 'deleted'))

    def on_moved(self, event):
        if not event.is_directory:
            asyncio.create_task(self._handle_file_change(event.dest_path, 'moved'))

    async def _handle_file_change(self, file_path: str, change_type: str):
        async with self.lock:
            self.pending_changes.add((file_path, change_type))

        await asyncio.sleep(1)  # Debounce rapid changes

        async with self.lock:
            if (file_path, change_type) in self.pending_changes:
                self.pending_changes.discard((file_path, change_type))

                if change_type == 'deleted':
                    await self.indexing_service.remove_from_index(file_path)
                else:
                    await self.indexing_service.index_file(Path(file_path))


class IndexingService:
    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.file_processor = FileProcessor()
        self.document_analyzer = DocumentAnalyzer()
        self.image_analyzer = ImageAnalyzer()
        self.db_session = db_session
        self.index_cache = {}
        self.monitored_paths: Set[Path] = set()
        self.observers = []
        self.indexing_queue = asyncio.Queue()
        self.worker_task = None

        self.supported_extensions = {
            '.txt', '.md', '.pdf', '.doc', '.docx',
            '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
            '.mp4', '.avi', '.mov', '.mkv',
            '.mp3', '.wav', '.flac',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.json', '.xml', '.csv', '.yaml', '.yml',
            '.py', '.js', '.java', '.cpp', '.c', '.html', '.css'
        }

    async def start(self):
        """Start the indexing service and background workers"""
        if not self.worker_task:
            self.worker_task = asyncio.create_task(self._process_indexing_queue())
        logger.info("Indexing service started")

    async def stop(self):
        """Stop the indexing service and clean up resources"""
        for observer in self.observers:
            observer.stop()
            observer.join()

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        logger.info("Indexing service stopped")

    async def index_directory(
        self,
        directory_path: Path,
        recursive: bool = True,
        monitor: bool = True
    ) -> Dict[str, Any]:
        """Index all files in a directory"""
        if not directory_path.exists() or not directory_path.is_dir():
            raise ValueError(f"Invalid directory path: {directory_path}")

        indexed_count = 0
        failed_count = 0
        skipped_count = 0

        # Start monitoring if requested
        if monitor and directory_path not in self.monitored_paths:
            self._start_monitoring(directory_path)

        # Get all files to index
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        files_to_index = []
        for file_path in directory_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                files_to_index.append(file_path)

        logger.info(f"Found {len(files_to_index)} files to index in {directory_path}")

        # Index files in batches
        batch_size = 10
        for i in range(0, len(files_to_index), batch_size):
            batch = files_to_index[i:i+batch_size]

            tasks = [self.index_file(file_path) for file_path in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    failed_count += 1
                    logger.error(f"Failed to index file: {result}")
                elif result.get('status') == 'indexed':
                    indexed_count += 1
                else:
                    skipped_count += 1

        return {
            'directory': str(directory_path),
            'total_files': len(files_to_index),
            'indexed': indexed_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'monitoring': monitor
        }

    async def index_file(self, file_path: Path) -> Dict[str, Any]:
        """Index a single file"""
        try:
            if not file_path.exists():
                return {'status': 'skipped', 'reason': 'File does not exist'}

            # Check if file is already indexed and up to date
            file_hash = await self._calculate_file_hash(file_path)
            if file_hash in self.index_cache:
                cached = self.index_cache[file_hash]
                if cached['modified_at'] >= file_path.stat().st_mtime:
                    return {'status': 'skipped', 'reason': 'Already indexed'}

            # Process the file
            analysis_result = await self.file_processor.process_file(
                file_path,
                organize=False,
                use_cache=False
            )

            # Extract content for search
            content = await self._extract_content(file_path, analysis_result)

            # Create indexed file entry
            indexed_file = IndexedFile(
                path=str(file_path),
                name=file_path.name,
                size=file_path.stat().st_size,
                mime_type=self._get_mime_type(file_path),
                created_at=datetime.fromtimestamp(file_path.stat().st_ctime),
                modified_at=datetime.fromtimestamp(file_path.stat().st_mtime),
                indexed_at=datetime.now(),
                content_hash=file_hash,
                metadata=analysis_result.get('analysis', {}),
                content=content,
                tags=analysis_result.get('analysis', {}).get('keywords', []),
                category=analysis_result.get('analysis', {}).get('category', 'general'),
                status=IndexStatus.INDEXED
            )

            # Save to database
            await self._save_to_database(indexed_file)

            # Update cache
            self.index_cache[file_hash] = {
                'path': str(file_path),
                'modified_at': file_path.stat().st_mtime,
                'indexed_at': datetime.now()
            }

            logger.info(f"Successfully indexed: {file_path}")
            return {
                'status': 'indexed',
                'file': indexed_file.to_dict()
            }

        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    async def remove_from_index(self, file_path: str) -> bool:
        """Remove a file from the index"""
        try:
            if self.db_session:
                await self.db_session.execute(
                    delete(FileIndex).where(FileIndex.file_path == file_path)
                )
                await self.db_session.commit()

            # Remove from cache
            for hash_key, cache_entry in list(self.index_cache.items()):
                if cache_entry['path'] == file_path:
                    del self.index_cache[hash_key]
                    break

            logger.info(f"Removed from index: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error removing file from index: {e}")
            return False

    async def update_index(self, file_path: Path) -> Dict[str, Any]:
        """Update the index for a modified file"""
        return await self.index_file(file_path)

    async def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current index"""
        try:
            total_files = len(self.index_cache)

            if self.db_session:
                result = await self.db_session.execute(
                    select(FileIndex)
                )
                db_files = result.scalars().all()

                total_size = sum(f.file_size for f in db_files)
                categories = {}
                for f in db_files:
                    cat = f.category or 'unknown'
                    categories[cat] = categories.get(cat, 0) + 1

                return {
                    'total_files': len(db_files),
                    'total_size_bytes': total_size,
                    'categories': categories,
                    'monitored_paths': [str(p) for p in self.monitored_paths],
                    'cache_size': len(self.index_cache)
                }

            return {
                'total_files': total_files,
                'cache_size': len(self.index_cache),
                'monitored_paths': [str(p) for p in self.monitored_paths]
            }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {'error': str(e)}

    def _start_monitoring(self, path: Path):
        """Start monitoring a directory for changes"""
        try:
            event_handler = FileSystemMonitor(self)
            observer = Observer()
            observer.schedule(event_handler, str(path), recursive=True)
            observer.start()

            self.observers.append(observer)
            self.monitored_paths.add(path)

            logger.info(f"Started monitoring: {path}")

        except Exception as e:
            logger.error(f"Error starting monitor for {path}: {e}")

    async def _extract_content(self, file_path: Path, analysis_result: Dict[str, Any]) -> str:
        """Extract searchable content from a file"""
        content_parts = []

        # Get text content from analysis
        if 'text' in analysis_result.get('analysis', {}):
            content_parts.append(analysis_result['analysis']['text'])

        if 'ocr_text' in analysis_result.get('analysis', {}):
            content_parts.append(analysis_result['analysis']['ocr_text'])

        if 'summary' in analysis_result.get('analysis', {}):
            content_parts.append(analysis_result['analysis']['summary'])

        # Add metadata as searchable content
        if 'metadata' in analysis_result.get('analysis', {}):
            metadata = analysis_result['analysis']['metadata']
            for key, value in metadata.items():
                if isinstance(value, str):
                    content_parts.append(f"{key}: {value}")

        # Add filename without extension
        content_parts.append(file_path.stem)

        return ' '.join(content_parts)

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()

        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def _get_mime_type(self, file_path: Path) -> str:
        """Get MIME type of a file"""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'

    async def _save_to_database(self, indexed_file: IndexedFile):
        """Save indexed file to database"""
        if not self.db_session:
            return

        try:
            # Check if file already exists in database
            result = await self.db_session.execute(
                select(FileIndex).where(FileIndex.file_path == indexed_file.path)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing record
                existing.file_name = indexed_file.name
                existing.file_size = indexed_file.size
                existing.mime_type = indexed_file.mime_type
                existing.content_hash = indexed_file.content_hash
                existing.metadata = indexed_file.metadata
                existing.content = indexed_file.content
                existing.tags = indexed_file.tags
                existing.category = indexed_file.category
                existing.indexed_at = indexed_file.indexed_at
                existing.status = indexed_file.status.value
            else:
                # Create new record
                file_index = FileIndex(
                    file_path=indexed_file.path,
                    file_name=indexed_file.name,
                    file_size=indexed_file.size,
                    mime_type=indexed_file.mime_type,
                    content_hash=indexed_file.content_hash,
                    metadata=indexed_file.metadata,
                    content=indexed_file.content,
                    tags=indexed_file.tags,
                    category=indexed_file.category,
                    created_at=indexed_file.created_at,
                    modified_at=indexed_file.modified_at,
                    indexed_at=indexed_file.indexed_at,
                    status=indexed_file.status.value
                )
                self.db_session.add(file_index)

            await self.db_session.commit()

        except Exception as e:
            logger.error(f"Error saving to database: {e}")
            await self.db_session.rollback()

    async def _process_indexing_queue(self):
        """Background worker to process indexing queue"""
        while True:
            try:
                file_path = await self.indexing_queue.get()
                await self.index_file(file_path)
                self.indexing_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in indexing worker: {e}")
                await asyncio.sleep(1)