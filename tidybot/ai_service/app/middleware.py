from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta
import time
import logging
import asyncio

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = datetime.now()
        
        async with self.lock:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < timedelta(minutes=1)
            ]
            
            if len(self.requests[client_ip]) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."}
                )
            
            self.requests[client_ip].append(current_time)
        
        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        request_id = f"{time.time()}-{request.client.host}"
        logger.info(f"Request {request_id}: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            
            logger.info(
                f"Request {request_id} completed: "
                f"status={response.status_code} "
                f"duration={process_time:.2f}ms"
            )
            
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            response.headers["X-Request-ID"] = request_id
            
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request {request_id} failed: "
                f"error={str(e)} "
                f"duration={process_time:.2f}ms"
            )
            raise


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key_header: str = "X-API-Key"):
        super().__init__(app)
        self.api_key_header = api_key_header
    
    async def dispatch(self, request: Request, call_next):
        exempt_paths = ["/", "/health", "/docs", "/openapi.json", "/redoc"]
        
        if request.url.path in exempt_paths:
            return await call_next(request)
        
        api_key = request.headers.get(self.api_key_header)
        
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "API key is required"}
            )
        
        # In production, validate against stored API keys
        # For now, we'll accept any non-empty key
        if not api_key:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key"}
            )
        
        response = await call_next(request)
        return response