from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from lib.db import connection as db
from services.legallens.pipeline.orchestrator import run_analyze_pipeline

router = APIRouter()

class AnalyzeRequest(BaseModel):
    contract_id: str
    s3_key: str
    org_id: str
    file_name: str
    mime_type: str

@router.post("/analyze")
async def analyze_contract(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    try:
        async with db.get_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO contracts (id, org_id, file_name, mime_type, status)
                VALUES ($1, $2, $3, $4, 'processing')
                ON CONFLICT (id) DO UPDATE SET status = 'processing'
            """,
                req.contract_id,
                req.org_id,
                req.file_name,
                req.mime_type,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    background_tasks.add_task(
        run_analyze_pipeline,
        req.contract_id,
        req.s3_key,
        req.org_id,
        req.file_name,
        req.mime_type,
    )
    return {"status": "processing", "contract_id": req.contract_id}
