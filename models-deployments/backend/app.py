from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import uuid
from datetime import datetime
import uvicorn

from config.logging_config import setup_logging, logger
from config.settings import settings
from utils.model_loader import load_all_models
from api.machine_learning import medical_charge, heart_disease, customer_churn,customer_uplift


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting FastAPI ML Server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    # Load all models
    load_all_models()
    
    logger.info("Server ready!")
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI ML Server...")
    

app = FastAPI(
    title="ML Models API",
    description="Production-ready ML model serving API",
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
    
    # Add request_id to request state
    request.state.request_id = request_id
    
    # Log incoming request
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
        
        # Log response
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
        
        # Add custom headers
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



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={"request_id": request_id},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


app.include_router(
    medical_charge.router,
    prefix="/medical-charge",
    tags=["Medical Charge Prediction"]
)

app.include_router(
    heart_disease.router,
    prefix="/heart-disease",
    tags=["Heart Disease Prediction"]
)

app.include_router(
    customer_churn.router,
    prefix="/customer-churn",
    tags=["Customer Churn Prediction"]
)

app.include_router(
    customer_uplift.router,
    prefix="/predict_uplift",
    tags=["uplift Prediction"]
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Machine Learning Models API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
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
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_level="info"
    )