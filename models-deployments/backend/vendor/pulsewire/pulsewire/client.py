# python/pulsewire/client.py
import atexit
import os
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx


class Pulsewire:
    """
    Sync/thread-based live log shipper.

    Safe to use from Flask, Django, plain scripts, or any sync codebase.
    A background daemon thread flushes the buffer on an interval so calls
    to .info()/.warn()/.error() never block on network I/O.
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

        self.enabled = enabled if enabled is not None else os.environ.get("ENV") == "production"

        self._queue: "queue.Queue" = queue.Queue(maxsize=max_queue_size)
        self._client = httpx.Client(timeout=5.0)
        self._stop = threading.Event()

        if self.enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            atexit.register(self.flush, final=True)
        else:
            self._thread = None

    def _enqueue(
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
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(record)
            except queue.Full:
                pass  # give up silently — never raise from logging

        if self._queue.qsize() >= self.max_batch_size:
            self.flush()

    def info(self, message: str, meta: Optional[Dict[str, Any]] = None, log_type: Optional[str] = None):
        self._enqueue("info", message, meta, log_type)

    def warn(self, message: str, meta: Optional[Dict[str, Any]] = None, log_type: Optional[str] = None):
        self._enqueue("warn", message, meta, log_type)

    def error(self, message: str, meta: Optional[Dict[str, Any]] = None, log_type: Optional[str] = None):
        self._enqueue("error", message, meta, log_type)

    def debug(self, message: str, meta: Optional[Dict[str, Any]] = None, log_type: Optional[str] = None):
        self._enqueue("debug", message, meta, log_type)

    def _run(self):
        while not self._stop.is_set():
            time.sleep(self.flush_interval)
            self.flush()

    def flush(self, final: bool = False):
        if not self.enabled:
            return

        batch = []
        while not self._queue.empty() and len(batch) < self.max_batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not batch:
            return

        try:
            self._client.post(
                self.endpoint,
                json={"logs": batch},
                headers=self.headers,
            )
        except Exception:
            if not final:
                for item in batch:
                    try:
                        self._queue.put_nowait(item)
                    except queue.Full:
                        break

    def close(self):
        if not self.enabled:
            return
        self._stop.set()
        self.flush(final=True)
        self._client.close()