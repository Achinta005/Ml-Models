import logging
import sys
import os
import asyncio
from loguru import logger as loguru_logger
from core.config import settings
from core.pulsewire_setup import pulsewire


class InterceptHandler(logging.Handler):
    """
    Default handler to intercept standard logging messages
    and route them to Loguru's logger.
    """
    def emit(self, record):
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


SKIP_ENDPOINTS = {"/", "/health"}

def _pulsewire_sink(message):
    """Loguru sink that forwards each log record to Pulsewire."""
    record = message.record

    endpoint = record["extra"].get("endpoint", "")
    if endpoint in SKIP_ENDPOINTS or endpoint.endswith(" /health") or endpoint == "/health":
        return

    level = record["level"].name.lower()
    text = record["message"]
    meta = {
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }
    meta.update({k: v for k, v in record["extra"].items() if k not in ("module", "function", "line")})
    if record["exception"]:
        meta["exception"] = str(record["exception"])

    method = {
        "info": pulsewire.info,
        "warning": pulsewire.warn,
        "error": pulsewire.error,
        "critical": pulsewire.error,
        "debug": pulsewire.debug,
    }.get(level, pulsewire.info)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(method(text, meta))
    except RuntimeError:
        pass  # no running loop yet (e.g. during early startup) — skip silently


def setup_logging():
    """Configure application logging using Loguru"""
    os.makedirs('logs', exist_ok=True)

    loguru_logger.remove()

    serialize_json = settings.LOG_FORMAT == "json"

    loguru_logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level> | <yellow>{extra}</yellow>",
        level=settings.LOG_LEVEL,
        colorize=True
    )

    loguru_logger.add(
        "logs/app.log",
        rotation="10 MB",
        level=settings.LOG_LEVEL,
        serialize=serialize_json
    )

    loguru_logger.add(
        "logs/error.log",
        rotation="10 MB",
        level="ERROR",
        serialize=serialize_json
    )

    loguru_logger.add(_pulsewire_sink, level=settings.LOG_LEVEL)

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

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