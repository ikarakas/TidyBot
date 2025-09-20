from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime
import json

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.database import get_db, Preset
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class PresetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    naming_pattern: str
    organization_rules: Dict[str, Any] = {}
    file_filters: Dict[str, Any] = {}


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    naming_pattern: Optional[str] = None
    organization_rules: Optional[Dict[str, Any]] = None
    file_filters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


@router.get("/")
async def list_presets(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    try:
        query = select(Preset).order_by(Preset.created_at.desc())
        
        if is_active is not None:
            query = query.where(Preset.is_active == is_active)
        
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        presets = result.scalars().all()
        
        return {
            'total': len(presets),
            'limit': limit,
            'offset': offset,
            'presets': [
                {
                    'id': preset.id,
                    'name': preset.name,
                    'description': preset.description,
                    'naming_pattern': preset.naming_pattern,
                    'organization_rules': preset.organization_rules,
                    'file_filters': preset.file_filters,
                    'is_active': preset.is_active,
                    'created_at': preset.created_at.isoformat(),
                    'updated_at': preset.updated_at.isoformat()
                }
                for preset in presets
            ]
        }
        
    except Exception as e:
        logger.error(f"Error listing presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{preset_id}")
async def get_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    try:
        result = await db.execute(
            select(Preset).where(Preset.id == preset_id)
        )
        preset = result.scalar_one_or_none()
        
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        return {
            'id': preset.id,
            'name': preset.name,
            'description': preset.description,
            'naming_pattern': preset.naming_pattern,
            'organization_rules': preset.organization_rules,
            'file_filters': preset.file_filters,
            'is_active': preset.is_active,
            'created_at': preset.created_at.isoformat(),
            'updated_at': preset.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching preset {preset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_preset(
    preset_data: PresetCreate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    
    try:
        existing = await db.execute(
            select(Preset).where(Preset.name == preset_data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Preset with this name already exists")
        
        preset = Preset(
            name=preset_data.name,
            description=preset_data.description,
            naming_pattern=preset_data.naming_pattern,
            organization_rules=preset_data.organization_rules,
            file_filters=preset_data.file_filters,
            is_active=True
        )
        
        db.add(preset)
        await db.commit()
        await db.refresh(preset)
        
        return {
            'id': preset.id,
            'name': preset.name,
            'message': 'Preset created successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating preset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{preset_id}")
async def update_preset(
    preset_id: int,
    preset_update: PresetUpdate,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    
    try:
        result = await db.execute(
            select(Preset).where(Preset.id == preset_id)
        )
        preset = result.scalar_one_or_none()
        
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        update_data = preset_update.dict(exclude_unset=True)
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            setattr(preset, key, value)
        
        await db.commit()
        
        return {"message": "Preset updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating preset {preset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{preset_id}")
async def delete_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    
    try:
        result = await db.execute(
            select(Preset).where(Preset.id == preset_id)
        )
        preset = result.scalar_one_or_none()
        
        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        await db.delete(preset)
        await db.commit()
        
        return {"message": "Preset deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting preset {preset_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/defaults/")
async def get_default_presets() -> Dict[str, Any]:
    
    defaults = [
        {
            'name': 'Screenshot Organizer',
            'description': 'Organize screenshots by date and content',
            'naming_pattern': 'screenshot_{description}_{date}',
            'organization_rules': {
                'strategy': 'by_date',
                'base_path': '~/Screenshots',
                'date_format': '%Y/%B'
            },
            'file_filters': {
                'extensions': ['png', 'jpg', 'jpeg'],
                'is_screenshot': True
            }
        },
        {
            'name': 'Document Archive',
            'description': 'Archive documents by type and date',
            'naming_pattern': '{category}_{title}_{date}',
            'organization_rules': {
                'strategy': 'by_category',
                'base_path': '~/Documents/Archive'
            },
            'file_filters': {
                'extensions': ['pdf', 'docx', 'txt']
            }
        },
        {
            'name': 'Photo Library',
            'description': 'Organize photos by date taken',
            'naming_pattern': '{date}_{description}',
            'organization_rules': {
                'strategy': 'by_date',
                'base_path': '~/Pictures',
                'date_format': '%Y/%m_%B'
            },
            'file_filters': {
                'extensions': ['jpg', 'jpeg', 'heic', 'raw', 'dng']
            }
        },
        {
            'name': 'Invoice Manager',
            'description': 'Organize invoices and receipts',
            'naming_pattern': 'invoice_{company}_{date}_{amount}',
            'organization_rules': {
                'strategy': 'by_category',
                'base_path': '~/Documents/Financial/Invoices'
            },
            'file_filters': {
                'keywords': ['invoice', 'receipt', 'bill']
            }
        }
    ]
    
    return {
        'total': len(defaults),
        'presets': defaults
    }