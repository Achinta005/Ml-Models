from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
import json

from services.polymind.pipeline.pipeline import run_injest_pipeline, run_query_pipeline, get_indexer
from core.logger import logger

router = APIRouter()

class IngestRequest(BaseModel):
    download_url: str
    doc_id: str
    filename: str
    user_id: str
    size_bytes: int

class DeleteRequest(BaseModel):
    doc_id: str

class QueryRequest(BaseModel):
    question: str
    document_ids: List[str]
    user_id: str
    top_k: Optional[int] = 3

@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(request: IngestRequest, background_tasks: BackgroundTasks):
    """Ingest document asynchronously"""
    background_tasks.add_task(
        run_injest_pipeline,
        download_url=request.download_url,
        doc_id=request.doc_id,
        filename=request.filename,
        user_id=request.user_id,
        size_bytes=request.size_bytes,
    )
    return {"doc_id": request.doc_id, "status": "processing"}

@router.delete("/index/{doc_id}")
async def delete_index(doc_id: str):
    """Delete document index from PolyMind"""
    try:
        get_indexer().delete(doc_id)
        return {"deleted": True, "doc_id": doc_id}
    except Exception as e:
        logger.error(f"Error deleting PolyMind index: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

@router.post("/query")
async def query_documents(request: QueryRequest):
    """Query PolyMind indexed documents"""
    try:
        messages, citations, _ = await run_query_pipeline(
            question=request.question,
            document_ids=request.document_ids,
            user_id=request.user_id,
            top_k=request.top_k or 3,
        )
        return {
            "success": True,
            "answer": "",
            "citations": citations,
            "messages": messages,
        }
    except Exception as e:
        logger.error(f"Error querying PolyMind: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
