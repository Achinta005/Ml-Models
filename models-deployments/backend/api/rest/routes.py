from fastapi import APIRouter
from api.rest.ml_models import (
    medical_charge,
    heart_disease,
    customer_churn,
    customer_uplift,
)
from api.rest.llm import llm
from api.rest.legallens.routes import router as legallens_router

api_router = APIRouter()

api_router.include_router(
    medical_charge.router, prefix="/medical-charge", tags=["Medical Charge Prediction"]
)

api_router.include_router(
    heart_disease.router, prefix="/heart-disease", tags=["Heart Disease Prediction"]
)

api_router.include_router(
    customer_churn.router, prefix="/customer-churn", tags=["Customer Churn Prediction"]
)

api_router.include_router(
    customer_uplift.router, prefix="/predict_uplift", tags=["uplift Prediction"]
)

api_router.include_router(llm.router, prefix="/api/llm", tags=["LLM - Llama 3.1"])


api_router.include_router(legallens_router, tags=["LegalLens"])
