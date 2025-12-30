import logging
import sys
import json
from datetime import datetime
import os
from config.settings import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName',
                          'relativeCreated', 'thread', 'threadName', 'exc_info',
                          'exc_text', 'stack_info']:
                log_data[key] = value
                
        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Simple text formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        return f"[{timestamp}] [{record.levelname}] {record.name} - {record.getMessage()}"


def setup_logging():
    """Configure application logging"""
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter based on settings
    if settings.LOG_FORMAT == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for all logs
    file_handler = logging.FileHandler('logs/app.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # File handler for errors only
    error_handler = logging.FileHandler('logs/error.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Suppress overly verbose loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    return root_logger

logger = setup_logging()