from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
import logging
import asyncio
import aiofiles
import sqlite3
from contextlib import asynccontextmanager
import hashlib
import pickle
from collections import deque

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    CONFLICT = "conflict"
    FAILED = "failed"


class OperationType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RENAME = "rename"
    MOVE = "move"


@dataclass
class OfflineOperation:
    id: str
    operation_type: OperationType
    file_path: str
    timestamp: datetime
    data: Dict[str, Any]
    status: SyncStatus
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self):
        return {
            'id': self.id,
            'operation_type': self.operation_type.value,
            'file_path': self.file_path,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'status': self.status.value,
            'error': self.error,
            'retry_count': self.retry_count
        }


class LocalCache:
    def __init__(self, cache_dir: str = "tidybot_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.db_path = self.cache_dir / "cache.db"
        self.file_cache_dir = self.cache_dir / "files"
        self.file_cache_dir.mkdir(exist_ok=True)

        self._init_database()
        self.memory_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'size_bytes': 0
        }

    def _init_database(self):
        """Initialize SQLite database for offline storage"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_cache (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                content TEXT,
                metadata TEXT,
                analysis_result TEXT,
                cached_at TIMESTAMP,
                accessed_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                size_bytes INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_cache (
                query_hash TEXT PRIMARY KEY,
                query_text TEXT,
                results TEXT,
                cached_at TIMESTAMP,
                accessed_at TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offline_queue (
                id TEXT PRIMARY KEY,
                operation_type TEXT,
                file_path TEXT,
                timestamp TIMESTAMP,
                data TEXT,
                status TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_cache_accessed
            ON file_cache(accessed_at)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_offline_queue_status
            ON offline_queue(status)
        ''')

        conn.commit()
        conn.close()

    async def cache_file(
        self,
        file_path: str,
        content: str,
        metadata: Dict[str, Any],
        analysis_result: Dict[str, Any]
    ) -> bool:
        """Cache file data for offline access"""
        try:
            file_hash = hashlib.sha256(file_path.encode()).hexdigest()

            # Store in SQLite
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO file_cache
                (file_path, file_hash, content, metadata, analysis_result,
                 cached_at, accessed_at, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_path,
                file_hash,
                content[:10000],  # Limit content size
                json.dumps(metadata),
                json.dumps(analysis_result),
                datetime.now(),
                datetime.now(),
                len(content)
            ))

            conn.commit()
            conn.close()

            # Update memory cache
            self.memory_cache[file_path] = {
                'content': content[:1000],
                'metadata': metadata,
                'analysis_result': analysis_result,
                'cached_at': datetime.now()
            }

            # Store actual file if it's small enough
            if len(content) < 1024 * 1024:  # 1MB limit
                cache_file_path = self.file_cache_dir / file_hash
                async with aiofiles.open(cache_file_path, 'w') as f:
                    await f.write(content)

            logger.info(f"Cached file: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error caching file {file_path}: {e}")
            return False

    async def get_cached_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached file data"""
        try:
            # Check memory cache first
            if file_path in self.memory_cache:
                self.cache_stats['hits'] += 1
                return self.memory_cache[file_path]

            # Check SQLite cache
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT content, metadata, analysis_result, file_hash
                FROM file_cache
                WHERE file_path = ?
            ''', (file_path,))

            row = cursor.fetchone()

            if row:
                # Update access stats
                cursor.execute('''
                    UPDATE file_cache
                    SET accessed_at = ?, access_count = access_count + 1
                    WHERE file_path = ?
                ''', (datetime.now(), file_path))

                conn.commit()
                conn.close()

                self.cache_stats['hits'] += 1

                # Check if full file is cached
                file_hash = row[3]
                cache_file_path = self.file_cache_dir / file_hash
                full_content = row[0]

                if cache_file_path.exists():
                    async with aiofiles.open(cache_file_path, 'r') as f:
                        full_content = await f.read()

                result = {
                    'content': full_content,
                    'metadata': json.loads(row[1]),
                    'analysis_result': json.loads(row[2])
                }

                # Update memory cache
                self.memory_cache[file_path] = result

                return result

            conn.close()
            self.cache_stats['misses'] += 1
            return None

        except Exception as e:
            logger.error(f"Error retrieving cached file {file_path}: {e}")
            return None

    async def cache_search_results(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> bool:
        """Cache search results for offline access"""
        try:
            query_hash = hashlib.sha256(query.encode()).hexdigest()

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO search_cache
                (query_hash, query_text, results, cached_at, accessed_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                query_hash,
                query,
                json.dumps(results),
                datetime.now(),
                datetime.now()
            ))

            conn.commit()
            conn.close()

            logger.info(f"Cached search results for query: {query[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Error caching search results: {e}")
            return False

    async def get_cached_search(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached search results"""
        try:
            query_hash = hashlib.sha256(query.encode()).hexdigest()

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT results, cached_at
                FROM search_cache
                WHERE query_hash = ?
            ''', (query_hash,))

            row = cursor.fetchone()

            if row:
                cached_at = datetime.fromisoformat(row[1])

                # Check if cache is still valid (24 hours)
                if datetime.now() - cached_at < timedelta(hours=24):
                    # Update access stats
                    cursor.execute('''
                        UPDATE search_cache
                        SET accessed_at = ?, access_count = access_count + 1
                        WHERE query_hash = ?
                    ''', (datetime.now(), query_hash))

                    conn.commit()
                    conn.close()

                    return json.loads(row[0])

            conn.close()
            return None

        except Exception as e:
            logger.error(f"Error retrieving cached search: {e}")
            return None

    async def cleanup_cache(self, max_age_days: int = 30, max_size_mb: int = 1000):
        """Clean up old or oversized cache entries"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Remove old entries
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            cursor.execute('''
                DELETE FROM file_cache
                WHERE accessed_at < ?
            ''', (cutoff_date,))

            cursor.execute('''
                DELETE FROM search_cache
                WHERE accessed_at < ?
            ''', (cutoff_date,))

            # Check total cache size
            cursor.execute('SELECT SUM(size_bytes) FROM file_cache')
            total_size = cursor.fetchone()[0] or 0

            if total_size > max_size_mb * 1024 * 1024:
                # Remove least recently used entries
                cursor.execute('''
                    DELETE FROM file_cache
                    WHERE file_path IN (
                        SELECT file_path FROM file_cache
                        ORDER BY accessed_at ASC
                        LIMIT (SELECT COUNT(*) / 4 FROM file_cache)
                    )
                ''')

            conn.commit()
            conn.close()

            # Clean up file cache directory
            for cache_file in self.file_cache_dir.glob('*'):
                if cache_file.stat().st_mtime < cutoff_date.timestamp():
                    cache_file.unlink()

            # Clear old entries from memory cache
            self.memory_cache = {
                k: v for k, v in self.memory_cache.items()
                if v['cached_at'] > cutoff_date
            }

            logger.info("Cache cleanup completed")

        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")


class OfflineManager:
    def __init__(self, cache_dir: str = "tidybot_cache"):
        self.cache = LocalCache(cache_dir)
        self.sync_queue = deque()
        self.is_online = True
        self.sync_task = None
        self.conflict_resolution_strategy = "server_wins"  # or "client_wins", "manual"

    async def start(self):
        """Start the offline manager"""
        # Load pending operations from database
        await self._load_pending_operations()

        # Start sync worker
        self.sync_task = asyncio.create_task(self._sync_worker())

        logger.info("Offline manager started")

    async def stop(self):
        """Stop the offline manager"""
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass

        logger.info("Offline manager stopped")

    async def queue_operation(
        self,
        operation_type: OperationType,
        file_path: str,
        data: Dict[str, Any]
    ) -> str:
        """Queue an operation for sync when online"""
        operation_id = hashlib.sha256(
            f"{file_path}{datetime.now()}".encode()
        ).hexdigest()[:16]

        operation = OfflineOperation(
            id=operation_id,
            operation_type=operation_type,
            file_path=file_path,
            timestamp=datetime.now(),
            data=data,
            status=SyncStatus.PENDING
        )

        # Save to database
        conn = sqlite3.connect(str(self.cache.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO offline_queue
            (id, operation_type, file_path, timestamp, data, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            operation.id,
            operation.operation_type.value,
            operation.file_path,
            operation.timestamp,
            json.dumps(operation.data),
            operation.status.value
        ))

        conn.commit()
        conn.close()

        # Add to memory queue
        self.sync_queue.append(operation)

        logger.info(f"Queued offline operation: {operation_id}")
        return operation_id

    async def sync_now(self) -> Dict[str, Any]:
        """Force sync of all pending operations"""
        if not self.is_online:
            return {
                'status': 'offline',
                'message': 'Cannot sync while offline'
            }

        synced = 0
        failed = 0
        conflicts = 0

        while self.sync_queue:
            operation = self.sync_queue.popleft()

            result = await self._sync_operation(operation)

            if result['status'] == 'success':
                synced += 1
            elif result['status'] == 'conflict':
                conflicts += 1
                await self._handle_conflict(operation, result)
            else:
                failed += 1
                operation.retry_count += 1

                if operation.retry_count < 3:
                    self.sync_queue.append(operation)

        return {
            'status': 'completed',
            'synced': synced,
            'failed': failed,
            'conflicts': conflicts
        }

    async def set_online_status(self, is_online: bool):
        """Update online/offline status"""
        self.is_online = is_online

        if is_online:
            logger.info("Going online, starting sync...")
            await self.sync_now()
        else:
            logger.info("Going offline, operations will be queued")

    async def _load_pending_operations(self):
        """Load pending operations from database"""
        try:
            conn = sqlite3.connect(str(self.cache.db_path))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, operation_type, file_path, timestamp, data, status, error, retry_count
                FROM offline_queue
                WHERE status IN (?, ?)
                ORDER BY timestamp ASC
            ''', (SyncStatus.PENDING.value, SyncStatus.FAILED.value))

            rows = cursor.fetchall()
            conn.close()

            for row in rows:
                operation = OfflineOperation(
                    id=row[0],
                    operation_type=OperationType(row[1]),
                    file_path=row[2],
                    timestamp=datetime.fromisoformat(row[3]),
                    data=json.loads(row[4]),
                    status=SyncStatus(row[5]),
                    error=row[6],
                    retry_count=row[7]
                )
                self.sync_queue.append(operation)

            logger.info(f"Loaded {len(rows)} pending operations")

        except Exception as e:
            logger.error(f"Error loading pending operations: {e}")

    async def _sync_worker(self):
        """Background worker to sync operations when online"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                if self.is_online and self.sync_queue:
                    await self.sync_now()

                # Periodic cache cleanup
                await self.cache.cleanup_cache()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync worker: {e}")

    async def _sync_operation(self, operation: OfflineOperation) -> Dict[str, Any]:
        """Sync a single operation with the server"""
        # This would be implemented to actually sync with the server
        # For now, returning a mock response
        return {
            'status': 'success',
            'operation_id': operation.id
        }

    async def _handle_conflict(
        self,
        operation: OfflineOperation,
        conflict_info: Dict[str, Any]
    ):
        """Handle sync conflicts"""
        if self.conflict_resolution_strategy == "server_wins":
            # Discard local changes
            logger.info(f"Conflict resolved: server wins for {operation.file_path}")

        elif self.conflict_resolution_strategy == "client_wins":
            # Retry with force flag
            operation.data['force'] = True
            self.sync_queue.append(operation)

        else:
            # Manual resolution needed
            logger.warning(f"Manual conflict resolution needed for {operation.file_path}")

    async def get_offline_stats(self) -> Dict[str, Any]:
        """Get statistics about offline operations"""
        return {
            'is_online': self.is_online,
            'pending_operations': len(self.sync_queue),
            'cache_stats': self.cache.cache_stats,
            'cache_size_mb': sum(
                f.stat().st_size for f in self.cache.file_cache_dir.glob('*')
            ) / (1024 * 1024)
        }