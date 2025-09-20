from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import shutil
import tempfile
import logging
from datetime import datetime
from pydantic import BaseModel, Field

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.database import get_db, ProcessingHistory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from services.file_processor import FileProcessor
from services.naming_engine import NamingRule, NamingPattern

logger = logging.getLogger(__name__)

router = APIRouter()

file_processor = FileProcessor()


class RenameRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file to rename")
    new_name: str = Field(..., description="New name for the file")
    create_backup: bool = Field(True, description="Create backup before renaming")
    update_index: bool = Field(True, description="Update search index after rename")


class BatchRenameRequest(BaseModel):
    operations: List[Dict[str, str]] = Field(..., description="List of rename operations")
    create_backup: bool = Field(True, description="Create backups before renaming")
    validate_first: bool = Field(True, description="Validate operations before executing")


class OrganizeRequest(BaseModel):
    file_path: str = Field(..., description="Path to the file to organize")
    base_directory: Optional[str] = Field(None, description="Base directory for organization")
    apply_changes: bool = Field(False, description="Apply the changes or just preview")


@router.post("/process")
async def process_file(
    file: UploadFile = File(...),
    organize: bool = Query(True, description="Apply organization rules"),
    use_cache: bool = Query(True, description="Use cached analysis if available"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)
        
        result = await file_processor.process_file(
            temp_path,
            organize=organize,
            use_cache=use_cache
        )
        
        history = ProcessingHistory(
            file_path=file.filename,
            original_name=file.filename,
            new_name=result.get('suggested_name', file.filename),
            processing_type='single',
            confidence_score=result.get('confidence_score', 0.0),
            file_metadata=result.get('analysis', {}),
            processing_time_ms=result.get('processing_time_ms', 0),
            status=result.get('status', 'completed')
        )
        db.add(history)
        await db.commit()
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file.name).exists():
            Path(temp_file.name).unlink()


@router.post("/rename")
async def rename_file(
    file: UploadFile = File(...),
    pattern: str = Query("content_based", description="Naming pattern to use"),
    template: Optional[str] = Query(None, description="Custom template for naming"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)
        
        try:
            naming_pattern = NamingPattern(pattern)
        except ValueError:
            naming_pattern = NamingPattern.CONTENT_BASED
        
        naming_rule = None
        if template:
            naming_rule = NamingRule(
                pattern=NamingPattern.CUSTOM_TEMPLATE,
                template=template,
                parameters={}
            )
        
        result = await file_processor.process_file(
            temp_path,
            naming_rule=naming_rule,
            organize=False,
            use_cache=True
        )
        
        return {
            'original_name': file.filename,
            'suggested_name': result.get('suggested_name'),
            'confidence_score': result.get('confidence_score'),
            'alternative_names': result.get('alternative_names', [])
        }
        
    except Exception as e:
        logger.error(f"Error renaming file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file.name).exists():
            Path(temp_file.name).unlink()


@router.get("/history")
async def get_processing_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    try:
        query = select(ProcessingHistory).order_by(ProcessingHistory.processed_at.desc())
        
        if status:
            query = query.where(ProcessingHistory.status == status)
        
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        history_items = result.scalars().all()
        
        return {
            'total': len(history_items),
            'limit': limit,
            'offset': offset,
            'items': [
                {
                    'id': item.id,
                    'original_name': item.original_name,
                    'new_name': item.new_name,
                    'confidence_score': item.confidence_score,
                    'processed_at': item.processed_at.isoformat(),
                    'status': item.status,
                    'file_path': item.file_path,
                    'file_type': item.file_metadata.get('type', 'document') if item.file_metadata else 'document'
                }
                for item in history_items
            ]
        }
        
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/clear")
async def clear_all_history(
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Clear all processing history"""
    try:
        # Delete all history records
        await db.execute(delete(ProcessingHistory))
        await db.commit()
        
        return {"message": "All history cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{history_id}")
async def delete_history_item(
    history_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    
    try:
        result = await db.execute(
            select(ProcessingHistory).where(ProcessingHistory.id == history_id)
        )
        history_item = result.scalar_one_or_none()
        
        if not history_item:
            raise HTTPException(status_code=404, detail="History item not found")
        
        await db.delete(history_item)
        await db.commit()
        
        return {"message": "History item deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting history item {history_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-name")
async def validate_filename(
    name: str = Query(..., description="Filename to validate"),
    os_type: str = Query("auto", description="Operating system type (windows, mac, linux, auto)")
) -> Dict[str, Any]:

    try:
        from app.utils.file_utils import sanitize_filename

        sanitized = sanitize_filename(name)
        is_valid = sanitized == name

        issues = []
        if not is_valid:
            if '<>:"/\\|?*' in name:
                issues.append("Contains invalid characters")
            if len(name) > 255:
                issues.append("Name too long (max 255 characters)")
            if name != name.strip('. '):
                issues.append("Invalid leading/trailing characters")

        return {
            'original': name,
            'sanitized': sanitized,
            'is_valid': is_valid,
            'issues': issues
        }

    except Exception as e:
        logger.error(f"Error validating filename: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename-on-disk")
async def rename_file_on_disk(
    request: RenameRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Actually rename a file on the disk
    """
    try:
        file_path = Path(request.file_path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

        result = await file_processor.apply_rename(
            file_path,
            request.new_name,
            create_backup=request.create_backup,
            update_index=request.update_index
        )

        # Save to history if successful
        if result.status.value == "success":
            history = ProcessingHistory(
                file_path=request.file_path,
                original_name=file_path.name,
                new_name=request.new_name,
                processing_type='rename',
                confidence_score=1.0,
                file_metadata={'rename_operation': True},
                processing_time_ms=0,
                status='completed'
            )
            db.add(history)
            await db.commit()

        return {
            'original_path': result.original_path,
            'new_path': result.new_path,
            'status': result.status.value,
            'error': result.error,
            'backup_path': result.backup_path,
            'timestamp': result.timestamp
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming file on disk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-rename-on-disk")
async def batch_rename_on_disk(
    request: BatchRenameRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Batch rename multiple files on disk
    """
    try:
        # Convert request operations to tuples
        rename_operations = [
            (Path(op['original_path']), op['new_name'])
            for op in request.operations
        ]

        result = await file_processor.apply_batch_rename(
            rename_operations,
            create_backup=request.create_backup,
            validate_first=request.validate_first
        )

        # Save successful renames to history
        if result['success']:
            for op_result in result['results']:
                if op_result['status'] == 'success':
                    original_path = Path(op_result['original_path'])
                    history = ProcessingHistory(
                        file_path=op_result['original_path'],
                        original_name=original_path.name,
                        new_name=Path(op_result['new_path']).name,
                        processing_type='batch_rename',
                        confidence_score=1.0,
                        file_metadata={'batch_operation': True},
                        processing_time_ms=0,
                        status='completed'
                    )
                    db.add(history)
            await db.commit()

        return result

    except Exception as e:
        logger.error(f"Error in batch rename: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/organize-and-rename")
async def organize_and_rename_file(
    request: OrganizeRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analyze file, suggest organization and renaming, optionally apply changes
    """
    try:
        file_path = Path(request.file_path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

        base_directory = Path(request.base_directory) if request.base_directory else None

        result = await file_processor.organize_and_rename(
            file_path,
            base_directory=base_directory,
            apply_changes=request.apply_changes
        )

        # Save to history if changes were applied
        if request.apply_changes and result.get('applied'):
            history = ProcessingHistory(
                file_path=request.file_path,
                original_name=file_path.name,
                new_name=result.get('suggested_name', file_path.name),
                processing_type='organize_rename',
                confidence_score=result.get('confidence_score', 0.0),
                file_metadata=result.get('analysis', {}),
                processing_time_ms=0,
                status='completed'
            )
            db.add(history)
            await db.commit()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error organizing and renaming file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/undo-last-operation")
async def undo_last_file_operation() -> Dict[str, Any]:
    """
    Undo the last file operation
    """
    try:
        result = await file_processor.file_operations.undo_last_operation()

        if result:
            return {
                'success': True,
                'undone_operation': {
                    'from': result.original_path,
                    'to': result.new_path,
                    'status': result.status.value
                }
            }
        else:
            return {
                'success': False,
                'message': 'No operation to undo or undo failed'
            }

    except Exception as e:
        logger.error(f"Error undoing operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))