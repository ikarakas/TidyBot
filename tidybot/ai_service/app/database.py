from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean, Text
from datetime import datetime
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# SQLite doesn't support pool_size and max_overflow parameters
if settings.database_url.startswith("sqlite"):
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


class ProcessingHistory(Base):
    __tablename__ = "processing_history"
    
    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    new_name = Column(String, nullable=False)
    processing_type = Column(String, nullable=False)
    confidence_score = Column(Float, default=0.0)
    file_metadata = Column(JSON, default={})
    processed_at = Column(DateTime, default=datetime.utcnow)
    processing_time_ms = Column(Integer, default=0)
    status = Column(String, default="completed")
    error_message = Column(Text, nullable=True)


class Preset(Base):
    __tablename__ = "presets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    naming_pattern = Column(String, nullable=False)
    organization_rules = Column(JSON, default={})
    file_filters = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FileAnalysisCache(Base):
    __tablename__ = "file_analysis_cache"

    id = Column(Integer, primary_key=True, index=True)
    file_hash = Column(String, unique=True, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    analysis_result = Column(JSON, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class FileIndex(Base):
    __tablename__ = "file_index"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String, unique=True, nullable=False, index=True)
    file_name = Column(String, nullable=False, index=True)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)
    content_hash = Column(String, nullable=False, index=True)
    file_metadata = Column(JSON, default={})
    content = Column(Text, nullable=True)
    tags = Column(JSON, default=[])
    category = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, nullable=False)
    modified_at = Column(DateTime, nullable=False)
    indexed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="indexed")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")


async def close_db():
    await engine.dispose()
    logger.info("Database connection closed")


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()