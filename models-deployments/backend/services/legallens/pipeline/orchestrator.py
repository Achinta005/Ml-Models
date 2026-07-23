import logging
import asyncio
import time
import os
import json
from pathlib import Path

from services.legallens.pipeline.extractor import LegalLensExtractor
from services.legallens.pipeline.segmenter import LegalLensSegmenter
from services.legallens.pipeline.classifier import LegalLensClassifier
from services.legallens.pipeline.llm import LegalLensLLM
from services.legallens.pipeline.vector_store import LegalLensVectorStore
from lib.db import connection as db
from core.config import settings

logger = logging.getLogger(__name__)

extractor = LegalLensExtractor()
segmenter = LegalLensSegmenter()
classifier = LegalLensClassifier()
llm = LegalLensLLM()
vector_store = LegalLensVectorStore()

async def run_analyze_pipeline(contract_id: str, s3_key: str, org_id: str, file_name: str, mime_type: str):
    import tempfile
    import shutil
    
    start_time = time.time()
    logger.info(f"Starting pipeline for contract {contract_id} ({file_name})")
    
    # Use the system's temporary directory for temporary storage
    base_temp_dir = Path(tempfile.gettempdir()) / "legal_lens" / org_id / contract_id
    base_temp_dir.mkdir(parents=True, exist_ok=True)
    local_path = base_temp_dir / file_name
    
    try:
        # 1. Download
        extractor.download_from_cloud(s3_key, local_path)
        
        if not local_path.exists():
            raise FileNotFoundError(f"File not found locally and Cloudinary download failed: {local_path}")
            
        # 2. Extract
        pages_data = await extractor.extract_text_async(str(local_path))
        
        # 3. Segment
        clauses = await asyncio.to_thread(segmenter.segment, pages_data)
        
        # 4. Classify
        clauses = await classifier.classify(clauses)
        
        # 5. Explain high/critical
        clauses = await llm.explain_clauses(clauses)
        
        # 6. Upsert to Qdrant
        await vector_store.upsert_clauses(org_id, contract_id, clauses)
        
        # 7. Write to Postgres
        await _save_to_postgres(contract_id, org_id, file_name, mime_type, clauses, start_time)
        
        # 8. Emit to NestJS WebSocket (Mocked for now)
        logger.info(f"MOCK: Emitting websocket event to NestJS for {contract_id}: status=done")
        
    except Exception as e:
        logger.error(f"Pipeline failed for {contract_id}: {e}")
        try:
            async with db.get_pool().acquire() as conn:
                await conn.execute("UPDATE contracts SET status = 'error' WHERE id = $1", contract_id)
        except Exception as db_e:
            logger.error(f"Failed to set error status in DB: {db_e}")
        raise e
    finally:
        # Cleanup the entire temporary contract directory
        if base_temp_dir.exists():
            try:
                shutil.rmtree(base_temp_dir)
            except Exception as e:
                logger.warning(f"Failed to delete temp directory {base_temp_dir}: {e}")

async def _save_to_postgres(contract_id: str, org_id: str, file_name: str, mime_type: str, clauses: list[dict], start_time: float):
    processing_time_ms = int((time.time() - start_time) * 1000)
    
    total = len(clauses)
    breakdown = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for c in clauses:
        rl = c.get("risk_label", "low")
        if rl in breakdown:
            breakdown[rl] += 1
            
    flagged = breakdown["high"] + breakdown["critical"]
    score = (breakdown["medium"]*1 + breakdown["high"]*3 + breakdown["critical"]*5) / max(total, 1) * 20
    score = min(max(int(score), 0), 100)
    
    async with db.get_pool().acquire() as conn:
        async with conn.transaction():
            # Upsert contract
            await conn.execute("""
                INSERT INTO contracts (id, org_id, file_name, mime_type, status, risk_score, total_clauses, flagged_clauses, risk_breakdown, processing_time_ms)
                VALUES ($1, $2, $3, $4, 'done', $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    status = 'done',
                    risk_score = EXCLUDED.risk_score,
                    total_clauses = EXCLUDED.total_clauses,
                    flagged_clauses = EXCLUDED.flagged_clauses,
                    risk_breakdown = EXCLUDED.risk_breakdown,
                    processing_time_ms = EXCLUDED.processing_time_ms
            """, contract_id, org_id, file_name, mime_type, score, total, flagged, json.dumps(breakdown), processing_time_ms)
            
            # Delete old clauses if replacing
            await conn.execute("DELETE FROM clauses WHERE contract_id = $1", contract_id)
            
            for c in clauses:
                await conn.execute("""
                    INSERT INTO clauses (id, contract_id, text, start_char, end_char, page_no, risk_label, risk_score, confidence, explanation)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, c["id"], contract_id, c["text"], c["start_char"], c["end_char"], c["page_no"], 
                c.get("risk_label"), int(c.get("confidence", 0)*100), c.get("confidence"), c.get("explanation"))
                
    logger.info(f"Saved {contract_id} to DB. Score: {score}, Time: {processing_time_ms}ms")
