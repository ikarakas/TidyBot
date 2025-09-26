from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = Field(default="TidyBot AI Service")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=11007)
    workers: int = Field(default=4)
    reload: bool = Field(default=False)
    
    database_url: str = Field(default="sqlite+aiosqlite:///./tidybot.db")
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=40)
    
    redis_url: Optional[str] = Field(default="redis://localhost:6379/0")
    cache_ttl: int = Field(default=3600)
    
    model_cache_dir: Path = Field(default=Path("./models"))
    use_gpu: bool = Field(default=False)
    batch_size: int = Field(default=32)
    max_workers: int = Field(default=4)
    
    tesseract_path: str = Field(default="/usr/bin/tesseract")
    ocr_languages: str = Field(default="eng,fra,spa,deu")
    
    max_file_size_mb: int = Field(default=100)
    allowed_extensions: str = Field(default="jpg,jpeg,png,gif,bmp,pdf,docx,txt,xlsx,pptx")
    temp_dir: Path = Field(default=Path("./temp"))
    
    secret_key: str = Field(default="change-this-in-production")
    api_key_header: str = Field(default="X-API-Key")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8080")
    
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=1000)
    rate_limit_period: int = Field(default=60)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        protected_namespaces = ('settings_',)  # Fix pydantic warning about model_ prefix
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]
    
    @property
    def ocr_languages_list(self) -> List[str]:
        return [lang.strip() for lang in self.ocr_languages.split(",")]
    
    def setup_directories(self):
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.setup_directories()