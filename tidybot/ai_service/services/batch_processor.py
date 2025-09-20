from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import uuid
from collections import deque

logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: Path = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class BatchJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tasks: List[ProcessingTask] = field(default_factory=list)
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    progress_percentage: float = 0.0


class BatchProcessor:
    def __init__(self, max_workers: int = 4, max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.processing_queue = asyncio.Queue(maxsize=max_queue_size)
        self.active_jobs: Dict[str, BatchJob] = {}
        self.completed_jobs: deque = deque(maxlen=100)
        self.workers = []
        self.is_running = False
        self.callbacks: Dict[str, List[Callable]] = {
            'on_task_complete': [],
            'on_task_failed': [],
            'on_job_complete': [],
            'on_progress': []
        }
    
    async def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Batch processor started with {self.max_workers} workers")
    
    async def stop(self):
        self.is_running = False
        
        for worker in self.workers:
            worker.cancel()
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        self.executor.shutdown(wait=True)
        logger.info("Batch processor stopped")
    
    async def create_batch_job(self, file_paths: List[Path], priority: int = 0) -> BatchJob:
        job = BatchJob()
        
        for file_path in file_paths:
            task = ProcessingTask(
                file_path=file_path,
                priority=priority
            )
            job.tasks.append(task)
        
        job.total_tasks = len(job.tasks)
        self.active_jobs[job.id] = job
        
        for task in job.tasks:
            await self.processing_queue.put((task.priority, task, job.id))
        
        logger.info(f"Created batch job {job.id} with {job.total_tasks} tasks")
        return job
    
    async def _worker(self, worker_id: str):
        logger.info(f"Worker {worker_id} started")
        
        while self.is_running:
            try:
                priority, task, job_id = await asyncio.wait_for(
                    self.processing_queue.get(), 
                    timeout=1.0
                )
                
                job = self.active_jobs.get(job_id)
                if not job:
                    continue
                
                await self._process_task(task, job)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _process_task(self, task: ProcessingTask, job: BatchJob):
        task.status = ProcessingStatus.PROCESSING
        task.started_at = datetime.now()
        
        try:
            from .file_processor import FileProcessor
            processor = FileProcessor()
            
            result = await processor.process_file(task.file_path)
            
            task.result = result
            task.status = ProcessingStatus.COMPLETED
            task.completed_at = datetime.now()
            
            job.completed_tasks += 1
            
            await self._trigger_callbacks('on_task_complete', task, job)
            
        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}")
            task.error = str(e)
            task.status = ProcessingStatus.FAILED
            task.completed_at = datetime.now()
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                task.status = ProcessingStatus.PENDING
                await self.processing_queue.put((task.priority - 1, task, job.id))
                logger.info(f"Retrying task {task.id} (attempt {task.retry_count})")
            else:
                job.failed_tasks += 1
                await self._trigger_callbacks('on_task_failed', task, job)
        
        job.progress_percentage = ((job.completed_tasks + job.failed_tasks) / job.total_tasks) * 100
        await self._trigger_callbacks('on_progress', job)
        
        if job.completed_tasks + job.failed_tasks >= job.total_tasks:
            await self._complete_job(job)
    
    async def _complete_job(self, job: BatchJob):
        job.status = ProcessingStatus.COMPLETED if job.failed_tasks == 0 else ProcessingStatus.FAILED
        job.completed_at = datetime.now()
        
        del self.active_jobs[job.id]
        self.completed_jobs.append(job)
        
        await self._trigger_callbacks('on_job_complete', job)
        logger.info(f"Job {job.id} completed: {job.completed_tasks} success, {job.failed_tasks} failed")
    
    async def _trigger_callbacks(self, event: str, *args):
        for callback in self.callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    callback(*args)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")
    
    def register_callback(self, event: str, callback: Callable):
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def get_job_status(self, job_id: str) -> Optional[BatchJob]:
        if job_id in self.active_jobs:
            return self.active_jobs[job_id]
        
        for job in self.completed_jobs:
            if job.id == job_id:
                return job
        
        return None
    
    def cancel_job(self, job_id: str) -> bool:
        if job_id not in self.active_jobs:
            return False
        
        job = self.active_jobs[job_id]
        
        for task in job.tasks:
            if task.status == ProcessingStatus.PENDING:
                task.status = ProcessingStatus.CANCELLED
        
        job.status = ProcessingStatus.CANCELLED
        job.completed_at = datetime.now()
        
        del self.active_jobs[job_id]
        self.completed_jobs.append(job)
        
        logger.info(f"Job {job_id} cancelled")
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        total_active_tasks = sum(len(job.tasks) for job in self.active_jobs.values())
        total_completed_tasks = sum(job.completed_tasks for job in self.completed_jobs)
        total_failed_tasks = sum(job.failed_tasks for job in self.completed_jobs)
        
        return {
            'active_jobs': len(self.active_jobs),
            'completed_jobs': len(self.completed_jobs),
            'active_tasks': total_active_tasks,
            'completed_tasks': total_completed_tasks,
            'failed_tasks': total_failed_tasks,
            'queue_size': self.processing_queue.qsize(),
            'max_queue_size': self.max_queue_size,
            'workers': self.max_workers,
            'is_running': self.is_running
        }