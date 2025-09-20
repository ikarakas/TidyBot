from fastapi import APIRouter
from .files import router as files_router
from .batch import router as batch_router
from .presets import router as presets_router
from .analysis import router as analysis_router
from .search import router as search_router

router = APIRouter()

router.include_router(files_router, prefix="/files", tags=["files"])
router.include_router(batch_router, prefix="/batch", tags=["batch"])
router.include_router(presets_router, prefix="/presets", tags=["presets"])
router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
router.include_router(search_router, prefix="/search", tags=["search"])