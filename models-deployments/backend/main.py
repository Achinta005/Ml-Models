from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import uuid
import threading
import asyncio
from datetime import datetime
import uvicorn

from core.logger import setup_logging, logger
from core.config import settings
from core.exceptions import global_exception_handler
from lib.db import connection as db
from api.rest.routes import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    await db.connect()
    await db.create_tables()

    logger.info("Server ready!")
    yield

    await db.disconnect()
    logger.info("Shutting down...")
    

app = FastAPI(
    title="Fast Api Server",
    description="Production-ready Fast Api Server for Ml models , LLm ,RAG etc.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "x-grant-key"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing"""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    request.state.request_id = request_id
    
    logger.info(
        f"Request started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host if request.client else "unknown",
        }
    )
    
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        )
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(duration_ms, 2))
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Request failed: {str(e)}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True
        )
        raise

app.add_exception_handler(Exception, global_exception_handler)

app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Machine Learning Models API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "uptime": time.time(),
        "timestamp": int(time.time() * 1000),
        "environment": settings.ENVIRONMENT
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_excludes=["data/*", "logs/*", "*.joblib", "*.pkl"],
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_level="info"
    )
