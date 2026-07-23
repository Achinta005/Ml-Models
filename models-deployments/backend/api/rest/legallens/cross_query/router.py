import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from lib.db import connection as db
from services.legallens.pipeline.llm import LegalLensLLM
from services.legallens.pipeline.vector_store import LegalLensVectorStore

router = APIRouter()

vector_store = LegalLensVectorStore()
llm = LegalLensLLM()

class CrossQueryRequest(BaseModel):
    matter_id: str
    contract_ids: List[str]
    question: str
    top_k_per_contract: int = 3

@router.post("/cross-query")
async def cross_query(req: CrossQueryRequest):
    if not req.contract_ids:
        raise HTTPException(status_code=400, detail="CONTRACT_IDS_CANNOT_BE_EMPTY")

    # Fetch contracts to verify they exist and belong to the same tenant org
    async with db.get_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, org_id FROM contracts WHERE id = ANY($1)", req.contract_ids
        )

    if not rows:
        raise HTTPException(status_code=404, detail="CONTRACTS_NOT_FOUND")

    # Ensure all found contracts belong to the same organization for tenant isolation
    org_id = rows[0]["org_id"]
    for row in rows:
        if row["org_id"] != org_id:
            raise HTTPException(
                status_code=403,
                detail="TENANT_ISOLATION_VIOLATION: All contracts must belong to the same organization"
            )

    # Search each contract concurrently
    try:
        tasks = [
            vector_store.search(org_id, cid, req.question, req.top_k_per_contract)
            for cid in req.contract_ids
        ]
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QDRANT_UNAVAILABLE: {e}")

    # Combine citations and raise errors if any search task failed
    all_citations = []
    for r in search_results:
        if isinstance(r, Exception):
            raise HTTPException(status_code=503, detail=f"QDRANT_UNAVAILABLE: {r}")
        all_citations.extend(r)

    if not all_citations:
        return {
            "answer": "I could not find relevant clauses across the specified contracts.",
            "citations": [],
            "found_relevant_clauses": False,
            "is_mock": False,
            "cited_indices": []
        }

    # Generate answer from LLM passing combined citations context
    qa_res = await llm.get_qa_answer(req.question, all_citations)
    
    return {
        "answer": qa_res.get("answer", ""),
        "citations": all_citations,
        "found_relevant_clauses": True,
        "is_mock": qa_res.get("is_mock", False),
        "cited_indices": qa_res.get("cited_indices", [])
    }
