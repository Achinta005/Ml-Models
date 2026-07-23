import logging
import sys
import os
from loguru import logger as loguru_logger
from core.config import settings

class InterceptHandler(logging.Handler):
    """
    Default handler to intercept standard logging messages
    and route them to Loguru's logger.
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    """Configure application logging using Loguru"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Remove default Loguru handler
    loguru_logger.remove()
    
    # Check if we should serialize to JSON (e.g. in production)
    serialize_json = settings.LOG_FORMAT == "json"
    
    # Add console handler (always clean and colorized for developer friendliness)
    loguru_logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True
    )
        
    # Add file handler for all logs
    loguru_logger.add(
        "logs/app.log",
        rotation="10 MB",
        level=settings.LOG_LEVEL,
        serialize=serialize_json
    )
    
    # Add file handler for error logs only
    loguru_logger.add(
        "logs/error.log",
        rotation="10 MB",
        level="ERROR",
        serialize=serialize_json
    )
    
    # Intercept all logs from standard logging library
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Set log level for root logger and suppress overly verbose loggers
    logging.getLogger().handlers = [InterceptHandler()]
    
    for name in ["uvicorn", "uvicorn.access", "watchfiles.main", "watchfiles", "qdrant_client", "httpx"]:
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False
        if name in ["watchfiles.main", "watchfiles", "uvicorn.access"]:
            logging.getLogger(name).setLevel(logging.WARNING)
        else:
            logging.getLogger(name).setLevel(getattr(logging, settings.LOG_LEVEL))
            
    return logging.getLogger("app")


logger = setup_logging()