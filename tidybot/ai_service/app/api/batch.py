from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pathlib import Path
import tempfile
import shutil
import logging
import asyncio

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from services.batch_processor import BatchProcessor, BatchJob, ProcessingStatus
from app.database import get_db, ProcessingHistory
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()

batch_processor = BatchProcessor(max_workers=4)


@router.on_event("startup")
async def startup_event():
    await batch_processor.start()


@router.on_event("shutdown")
async def shutdown_event():
    await batch_processor.stop()


@router.post("/process")
async def create_batch_job(
    files: List[UploadFile] = File(...),
    priority: int = Query(0, description="Job priority (higher = more important)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    temp_files = []
    
    try:
        for upload_file in files:
            with tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=Path(upload_file.filename).suffix
            ) as temp_file:
                shutil.copyfileobj(upload_file.file, temp_file)
                temp_files.append(Path(temp_file.name))
        
        job = await batch_processor.create_batch_job(temp_files, priority)
        
        background_tasks.add_task(cleanup_temp_files, temp_files, delay=3600)
        
        return {
            'job_id': job.id,
            'status': job.status.value,
            'total_tasks': job.total_tasks,
            'message': f'Batch job created with {job.total_tasks} files'
        }
        
    except Exception as e:
        for temp_file in temp_files:
            if temp_file.exists():
                temp_file.unlink()
        
        logger.error(f"Error creating batch job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    
    job = batch_processor.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        'job_id': job.id,
        'status': job.status.value,
        'total_tasks': job.total_tasks,
        'completed_tasks': job.completed_tasks,
        'failed_tasks': job.failed_tasks,
        'progress_percentage': job.progress_percentage,
        'created_at': job.created_at.isoformat(),
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'tasks': [
            {
                'id': task.id,
                'file_path': str(task.file_path),
                'status': task.status.value,
                'error': task.error
            }
            for task in job.tasks[:10]
        ] if job.total_tasks <= 10 else []
    }


@router.get("/jobs")
async def list_jobs(
    include_completed: bool = Query(True, description="Include completed jobs"),
    limit: int = Query(50, ge=1, le=100)
) -> Dict[str, Any]:
    
    jobs = []
    
    for job in batch_processor.active_jobs.values():
        jobs.append({
            'job_id': job.id,
            'status': job.status.value,
            'total_tasks': job.total_tasks,
            'progress_percentage': job.progress_percentage,
            'created_at': job.created_at.isoformat()
        })
    
    if include_completed:
        for job in list(batch_processor.completed_jobs)[-limit:]:
            jobs.append({
                'job_id': job.id,
                'status': job.status.value,
                'total_tasks': job.total_tasks,
                'completed_tasks': job.completed_tasks,
                'failed_tasks': job.failed_tasks,
                'created_at': job.created_at.isoformat(),
                'completed_at': job.completed_at.isoformat() if job.completed_at else None
            })
    
    return {
        'total': len(jobs),
        'jobs': jobs
    }


@router.delete("/cancel/{job_id}")
async def cancel_job(job_id: str) -> Dict[str, str]:
    
    if batch_processor.cancel_job(job_id):
        return {"message": f"Job {job_id} cancelled successfully"}
    else:
        raise HTTPException(status_code=404, detail="Job not found or already completed")


@router.get("/results/{job_id}")
async def get_job_results(
    job_id: str,
    include_failed: bool = Query(True, description="Include failed tasks in results")
) -> Dict[str, Any]:
    
    job = batch_processor.get_job_status(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Job not yet completed")
    
    results = []
    
    for task in job.tasks:
        if task.status == ProcessingStatus.COMPLETED:
            results.append({
                'task_id': task.id,
                'file_path': str(task.file_path),
                'status': 'success',
                'result': task.result
            })
        elif include_failed and task.status == ProcessingStatus.FAILED:
            results.append({
                'task_id': task.id,
                'file_path': str(task.file_path),
                'status': 'failed',
                'error': task.error
            })
    
    return {
        'job_id': job.id,
        'total_results': len(results),
        'results': results
    }


@router.get("/statistics")
async def get_batch_statistics() -> Dict[str, Any]:
    return batch_processor.get_statistics()


async def cleanup_temp_files(file_paths: List[Path], delay: int = 0):
    if delay > 0:
        await asyncio.sleep(delay)
    
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {file_path}: {e}")