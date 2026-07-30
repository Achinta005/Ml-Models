# pulsewire (Python)

Lightweight live log shipper for Python. Ships with a sync client
(thread-based) and an async client (asyncio-native) for fast servers.

## Install

```bash
pip install pulsewire
```

(Once published — for now, install locally: `pip install -e ./python`)

## Sync usage (Flask, Django, plain scripts)

```python
from pulsewire import Pulsewire

logger = Pulsewire(
    endpoint="https://logs.myserver.com/ingest",
    service_name="auth-service",
)

logger.info("User logged in", {"user_id": 123})
logger.warn("Slow query", {"ms": 820})
logger.error("DB connection failed", {"retry": 2})

# on shutdown
logger.close()
```

## Async usage (FastAPI / fast servers)

```python
from fastapi import FastAPI
from pulsewire import AsyncPulsewire

app = FastAPI()
logger = AsyncPulsewire(
    endpoint="https://logs.myserver.com/ingest",
    service_name="orders-api",
)

@app.on_event("startup")
async def startup():
    logger.start()

@app.on_event("shutdown")
async def shutdown():
    await logger.close()

@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    await logger.info("Fetching order", {"order_id": order_id})
    ...
```

## Options (both clients)

| Option           | Default | Description                                    |
|------------------|---------|--------------------------------------------------|
| `endpoint`       | —       | Collector URL (required)                        |
| `service_name`   | —       | Logical service name attached to every log (required) |
| `flush_interval` | `3.0`   | Seconds between automatic flushes                |
| `max_batch_size` | `50`    | Logs per batch; also triggers an early flush     |
| `max_queue_size` | `500`   | Hard cap on buffered logs (oldest dropped past this) |
| `headers`        | `{}`    | Extra headers, e.g. an auth token                |

## Why two clients?

- `Pulsewire` uses a background **thread** + blocking `httpx.Client` —
  simplest option, works in any sync codebase without an event loop.
- `AsyncPulsewire` uses an **asyncio task** + `httpx.AsyncClient` — avoids
  spinning up a thread in an already-async process, and never risks
  blocking the event loop that's serving your requests.

Both send the same wire format — see [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
