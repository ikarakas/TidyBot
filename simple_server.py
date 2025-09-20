#!/usr/bin/env python3
"""
Simple TidyBot Server - Minimal implementation for CLI testing
"""

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import random

app = FastAPI(title="TidyBot Simple Server")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "TidyBot AI Service", "version": "1.0.0"}

@app.post("/api/v1/files/process")
async def process_file(file: UploadFile = File(...)):
    """Simple file processing endpoint for testing"""

    # Get file extension
    ext = file.filename.split('.')[-1] if '.' in file.filename else ''

    # Generate suggestions based on file type
    suggestions = {
        'pdf': f"Document_{datetime.now().strftime('%Y%m%d')}_{file.filename}",
        'jpg': f"Image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
        'png': f"Screenshot_{datetime.now().strftime('%Y-%m-%d_%H.%M.%S')}.png",
        'txt': f"TextFile_{datetime.now().strftime('%Y%m%d')}.txt",
    }

    suggested_name = suggestions.get(ext, f"File_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")

    # Determine category
    categories = {
        'pdf': 'document',
        'doc': 'document',
        'docx': 'document',
        'jpg': 'image',
        'png': 'screenshot' if 'screenshot' in file.filename.lower() else 'image',
        'txt': 'document',
    }

    return {
        "suggested_name": suggested_name,
        "confidence_score": random.uniform(0.6, 0.95),
        "category": categories.get(ext, 'unknown'),
        "organization": {
            "suggested_path": f"{categories.get(ext, 'misc')}/{datetime.now().year}"
        },
        "date_extracted": datetime.now().isoformat()
    }

@app.get("/api/v1/presets/")
async def get_presets():
    return [
        {"id": "default", "name": "Default", "description": "General purpose"},
        {"id": "screenshot", "name": "Screenshot", "description": "Screenshot organization"},
        {"id": "document", "name": "Document", "description": "Document filing"},
        {"id": "photo", "name": "Photo", "description": "Photo library"}
    ]

if __name__ == "__main__":
    print("Starting Simple TidyBot Server on http://127.0.0.1:11007")
    uvicorn.run(app, host="0.0.0.0", port=11007)