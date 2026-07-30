# python/pulsewire/async_client.py
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx


class AsyncPulsewire:
    """
    Asyncio-native live log shipper for fast async servers (FastAPI,
    Starlette, aiohttp). Buffers in an in-process list guarded by an
    asyncio.Lock and flushes via a background asyncio task, so logging
    calls never block the event loop on network I/O.

    Call `.start()` once from within a running event loop (e.g. a FastAPI
    startup event) before using `.info()/.warn()/.error()`.
    """

    def __init__(
        self,
        endpoint: str,
        service_name: str,
        flush_interval: float = 15.0,
        max_batch_size: int = 300,
        max_queue_size: int = 2000,
        headers: Optional[Dict[str, str]] = None,
        enabled: Optional[bool] = None,
    ):
        if not endpoint:
            raise ValueError("pulsewire: `endpoint` is required")
        if not service_name:
            raise ValueError("pulsewire: `service_name` is required")

        self.endpoint = endpoint
        self.service_name = service_name
        self.flush_interval = flush_interval
        self.max_batch_size = max_batch_size
        self.max_queue_size = max_queue_size
        self.headers = headers or {}

        self.enabled = (
            enabled if enabled is not None else os.environ.get("ENV") == "production"
        )

        self._buffer: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient(timeout=5.0)
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Call once from inside a running event loop."""
        if not self.enabled:
            return
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _enqueue(
        self,
        level: str,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        log_type: Optional[str] = None,
    ):
        if not self.enabled:
            return

        record = {
            "service": self.service_name,
            "type": log_type,
            "level": level,
            "message": message,
            "meta": meta or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        should_flush = False
        async with self._lock:
            self._buffer.append(record)
            if len(self._buffer) > self.max_queue_size:
                self._buffer = self._buffer[-self.max_queue_size :]  # drop oldest
            should_flush = len(self._buffer) >= self.max_batch_size

        if should_flush:
            await self.flush()

    async def info(
        self,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        log_type: Optional[str] = None,
    ):
        await self._enqueue("info", message, meta, log_type)

    async def warn(
        self,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        log_type: Optional[str] = None,
    ):
        await self._enqueue("warn", message, meta, log_type)

    async def error(
        self,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        log_type: Optional[str] = None,
    ):
        await self._enqueue("error", message, meta, log_type)

    async def debug(
        self,
        message: str,
        meta: Optional[Dict[str, Any]] = None,
        log_type: Optional[str] = None,
    ):
        await self._enqueue("debug", message, meta, log_type)

    async def _run(self):
        while True:
            await asyncio.sleep(self.flush_interval)
            await self.flush()

    async def flush(self):
        if not self.enabled:
            return

        async with self._lock:
            if not self._buffer:
                return
            batch, self._buffer = (
                self._buffer[: self.max_batch_size],
                self._buffer[self.max_batch_size :],
            )

        try:
            await self._client.post(
                self.endpoint,
                json={"logs": batch},
                headers=self.headers,
            )
        except Exception:
            async with self._lock:
                merged = batch + self._buffer
                self._buffer = (
                    merged[-self.max_queue_size :]
                    if len(merged) > self.max_queue_size
                    else merged
                )

    async def close(self):
        if not self.enabled:
            return
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.flush()
        await self._client.aclose()
