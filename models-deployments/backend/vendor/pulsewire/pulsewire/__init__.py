# python/pulsewire/__init__.py
"""
Pulsewire — lightweight live log shipper.

Use `Pulsewire` for sync apps (Flask, Django, plain scripts) — it flushes
on a background thread so calling code never blocks.

Use `AsyncPulsewire` for asyncio apps (FastAPI, Starlette) — it flushes
via an asyncio task on the running event loop.
"""

from .client import Pulsewire
from .async_client import AsyncPulsewire

__all__ = ["Pulsewire", "AsyncPulsewire"]
__version__ = "0.1.0"