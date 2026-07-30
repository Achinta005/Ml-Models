from core.config import settings
from pulsewire.async_client import AsyncPulsewire

pulsewire = AsyncPulsewire(
    endpoint="https://pulsewire-worker.server-achinta-gateway.workers.dev/ingest",
    service_name="fastapi-server",
    headers={"x-pulsewire-key": settings.PULSEWIRE_INGEST_KEY},
    enabled=(settings.ENVIRONMENT == "production"),
)