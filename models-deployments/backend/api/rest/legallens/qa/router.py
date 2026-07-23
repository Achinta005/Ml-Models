from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from lib.db import connection as db
from services.legallens.pipeline.llm import LegalLensLLM
from services.legallens.pipeline.vector_store import LegalLensVectorStore

router = APIRouter()

vector_store = LegalLensVectorStore()
llm = LegalLensLLM()

class QARequest(BaseModel):
    contract_id: str
    question: str
    conversation_history: List[dict] = []
    top_k: int = 5

@router.post("/qa")
async def qa(req: QARequest):
    async with db.get_pool().acquire() as conn:
        org_id = await conn.fetchval(
            "SELECT org_id FROM contracts WHERE id = $1", req.contract_id
        )
    if not org_id:
        raise HTTPException(status_code=404, detail="CONTRACT_NOT_FOUND")

    try:
        citations = await vector_store.search(
            org_id, req.contract_id, req.question, req.top_k
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="QDRANT_UNAVAILABLE")

    if not citations:
        return {
            "answer": "I could not find relevant clauses.",
            "citations": [],
            "found_relevant_clauses": False,
        }

    qa_res = await llm.get_qa_answer(req.question, citations, req.conversation_history)
    return {
        "answer": qa_res.get("answer", ""),
        "citations": citations,
        "found_relevant_clauses": True,
        "is_mock": qa_res.get("is_mock", False),
        "cited_indices": qa_res.get("cited_indices", [])
    }
