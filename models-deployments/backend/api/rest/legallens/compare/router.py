from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class CompareRequest(BaseModel):
    contract_id: str
    template_id: str
    org_id: str
    similarity_threshold: float = 0.78

@router.post("/compare")
async def compare_template(req: CompareRequest):
    return {"message": "Mock compare response", "match_score": 100}
