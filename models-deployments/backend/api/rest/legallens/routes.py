from fastapi import APIRouter, Depends

from api.rest.legallens.auth import get_api_key
from api.rest.legallens.analyze.router import router as analyze_router
from api.rest.legallens.qa.router import router as qa_router
from api.rest.legallens.cross_query.router import router as cross_query_router
from api.rest.legallens.export.router import router as export_router
from api.rest.legallens.get_clauses.router import router as get_router
from api.rest.legallens.compare.router import router as compare_router

router = APIRouter(
    prefix="/legallens",
    tags=["LegalLens"],
    dependencies=[Depends(get_api_key)]
)

router.include_router(analyze_router)
router.include_router(qa_router)
router.include_router(cross_query_router)
router.include_router(export_router)
router.include_router(get_router)
router.include_router(compare_router)

