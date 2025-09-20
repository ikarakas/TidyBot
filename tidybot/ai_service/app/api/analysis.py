from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from pathlib import Path
import tempfile
import shutil
import logging

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from services.image_analyzer import ImageAnalyzer
from services.document_analyzer import DocumentAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter()

image_analyzer = ImageAnalyzer()
document_analyzer = DocumentAnalyzer()


@router.post("/image")
async def analyze_image(
    file: UploadFile = File(...),
    extract_text: bool = Query(True, description="Extract text using OCR"),
    detect_objects: bool = Query(True, description="Detect objects in image"),
    generate_caption: bool = Query(True, description="Generate image caption")
) -> Dict[str, Any]:
    
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)
        
        result = await image_analyzer.analyze(temp_path)
        
        if not extract_text:
            result.pop('ocr_text', None)
        if not detect_objects:
            result.pop('objects', None)
        if not generate_caption:
            result.pop('caption', None)
        
        return {
            'filename': file.filename,
            'content_type': file.content_type,
            'analysis': result
        }
        
    except Exception as e:
        logger.error(f"Error analyzing image {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file.name).exists():
            Path(temp_file.name).unlink()


@router.post("/document")
async def analyze_document(
    file: UploadFile = File(...),
    extract_keywords: bool = Query(True, description="Extract keywords"),
    extract_dates: bool = Query(True, description="Extract dates"),
    generate_summary: bool = Query(True, description="Generate summary")
) -> Dict[str, Any]:
    
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)
        
        result = await document_analyzer.analyze(temp_path)
        
        if not extract_keywords:
            result.pop('keywords', None)
        if not extract_dates:
            result.pop('dates', None)
        if not generate_summary:
            result.pop('summary', None)
        
        return {
            'filename': file.filename,
            'content_type': file.content_type,
            'analysis': result
        }
        
    except Exception as e:
        logger.error(f"Error analyzing document {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file.name).exists():
            Path(temp_file.name).unlink()


@router.post("/quick-scan")
async def quick_scan(
    file: UploadFile = File(...)
) -> Dict[str, Any]:
    
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)
        
        from app.utils.file_utils import get_file_type, get_file_metadata
        
        mime_type, category = get_file_type(temp_path)
        metadata = get_file_metadata(temp_path)
        
        return {
            'filename': file.filename,
            'mime_type': mime_type,
            'category': category,
            'metadata': metadata
        }
        
    except Exception as e:
        logger.error(f"Error scanning file {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file and Path(temp_file.name).exists():
            Path(temp_file.name).unlink()