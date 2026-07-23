import logging
import uuid
import re
import hashlib
from typing import Any
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from core.config import settings

logger = logging.getLogger(__name__)

# Strict validation pattern for org_id: alphanumeric, underscores, hyphens, up to 64 chars
ORG_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

def validate_org_id(org_id: str):
    if not org_id or not ORG_ID_PATTERN.match(org_id):
        raise ValueError(f"Invalid org_id: {org_id}. Must be alphanumeric, underscores, or hyphens, up to 64 chars.")

def get_deterministic_mock_embedding(text: str, dim: int) -> list[float]:
    """Generates a normalized, deterministic mock embedding based on the text hash."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(dim):
        val = (h[i % len(h)] + i) % 256
        vec.append(round((val / 255.0) * 2.0 - 1.0, 4))
    return vec

class LegalLensVectorStore:
    def __init__(self):
        url = settings.QDRANT_URL if settings.QDRANT_URL else ":memory:"
        
        # Enable cloud inference only for remote Qdrant Cloud endpoints
        self.use_cloud_inference = url != ":memory:" and "localhost" not in url and "127.0.0.1" not in url
        self.dim_size = 384
        
        self.qdrant: Any = AsyncQdrantClient(
            url=url,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            cloud_inference=self.use_cloud_inference
        )
        logger.info(f"LegalLensVectorStore initialized (Cloud Inference: {self.use_cloud_inference})")

    async def _ensure_collection(self, collection_name: str):
        try:
            await self.qdrant.get_collection(collection_name)
        except Exception:
            logger.info(f"Creating Qdrant collection: {collection_name}")
            try:
                await self.qdrant.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=self.dim_size, distance=models.Distance.COSINE)
                )
            except Exception as ce:
                # Handle concurrency race condition if another process created it concurrently
                if "already exists" in str(ce).lower():
                    logger.info(f"Collection {collection_name} was created concurrently.")
                else:
                    raise

        # Always ensure a keyword payload index exists on contract_id for filtering
        try:
            await self.qdrant.create_payload_index(
                collection_name=collection_name,
                field_name="contract_id",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
        except Exception as ie:
            logger.debug(f"Payload index creation note (might already exist): {ie}")

    async def upsert_clauses(self, org_id: str, contract_id: str, clauses: list[dict]):
        validate_org_id(org_id)
        if not clauses:
            return

        collection_name = f"org_{org_id.replace('-', '_')}"
        await self._ensure_collection(collection_name)

        points = []
        for i, clause in enumerate(clauses):
            clause_id = clause.get("id") or str(uuid.uuid4())
            clause["id"] = clause_id  # attach generated ID back to dict if missing
            
            if self.use_cloud_inference:
                # Delegate embedding generation to Qdrant Cloud Inference
                vector = models.Document(
                    text=clause["text"],
                    model="sentence-transformers/all-minilm-l6-v2"
                )
            else:
                # Local/fallback mode: use deterministic mock embedding
                vector = get_deterministic_mock_embedding(clause["text"], self.dim_size)

            points.append(models.PointStruct(
                id=clause_id,
                vector=vector,
                payload={
                    "contract_id": contract_id,
                    "clause_index": i,
                    "page_no": clause["page_no"],
                    "text": clause["text"]
                }
            ))

        # Batch upsert points to prevent timeout/oversized payload issues
        batch_size = 100
        for i in range(0, len(points), batch_size):
            sub_points = points[i : i + batch_size]
            try:
                await self.qdrant.upsert(collection_name=collection_name, points=sub_points)
                logger.info(f"Upserted batch of {len(sub_points)} clause vectors into {collection_name} for contract {contract_id}")
            except Exception as e:
                logger.error(f"Qdrant batch upsert failed: {e}")
                raise

    async def search(self, org_id: str, contract_id: str | None = None, query: str = "", top_k: int = 5) -> list[dict]:
        validate_org_id(org_id)
        collection_name = f"org_{org_id.replace('-', '_')}"
        await self._ensure_collection(collection_name)
        
        try:
            if self.use_cloud_inference:
                query_vector = models.Document(
                    text=query,
                    model="sentence-transformers/all-minilm-l6-v2"
                )
            else:
                query_vector = get_deterministic_mock_embedding(query, self.dim_size)
            
            # Optional filter by contract_id
            q_filter = None
            if contract_id:
                q_filter = models.Filter(
                    must=[models.FieldCondition(key="contract_id", match=models.MatchValue(value=contract_id))]
                )
                
            response = await self.qdrant.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=q_filter,
                limit=top_k
            )
            results = response.points
            
            # Format output and verify tenant isolation (defense-in-depth)
            formatted = []
            for hit in results:
                hit_contract_id = hit.payload.get("contract_id")
                if contract_id and hit_contract_id != contract_id:
                    logger.warning(f"Tenant isolation mismatch: expected contract {contract_id}, retrieved {hit_contract_id}")
                    continue
                
                formatted.append({
                    "clause_id": hit.id,
                    "contract_id": hit_contract_id,
                    "page_no": hit.payload.get("page_no"),
                    "text": hit.payload.get("text"),
                    "relevance_score": hit.score
                })
            return formatted
            
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            raise
