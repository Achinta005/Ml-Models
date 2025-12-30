from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict
import pandas as pd

from utils.model_loader import models
from config.logging_config import logger

router = APIRouter()


def should_send_ad(uplift_value: float, threshold: float = 0.01) -> str:
    if uplift_value > threshold:
        return "Send Ad (user likely to respond positively)"
    elif uplift_value < -threshold:
        return "Do NOT send Ad (ad may reduce conversion)"
    return "Neutral - no significant effect"


class CustomerUpliftRequest(BaseModel):
    age: float = Field(..., ge=0)
    monthlyIncome: float = Field(..., ge=0)
    tenure: float = Field(..., ge=0)
    engagementScore: float
    sessionTime: float
    activityChange: float
    churnRisk: float
    appVisitsPerWeek: float
    regionCode: float
    totalClicks: float
    customerRating: float
    satisfactionTrend: float

    class Config:
        json_schema_extra = {
            "example": {
                "age": 35,
                "monthlyIncome": 50000,
                "tenure": 12,
                "engagementScore": 0.7,
                "sessionTime": 15,
                "activityChange": 0.1,
                "churnRisk": 0.2,
                "appVisitsPerWeek": 5,
                "regionCode": 2,
                "totalClicks": 30,
                "customerRating": 4.5,
                "satisfactionTrend": 0.3
            }
        }


class CustomerUpliftResponse(BaseModel):
    success: bool
    treated_probability: float
    control_probability: float
    predicted_uplift: float
    decision: str



@router.post(
    "/predict",
    response_model=CustomerUpliftResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_customer_uplift(request: CustomerUpliftRequest):
    """Predict customer uplift and ad decision"""
    try:
        # Check if models are loaded
        if (
            models.uplift_treated_model is None
            or models.uplift_control_model is None
        ):
            logger.error("Uplift models not loaded")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Uplift models not loaded. Please contact administrator.",
            )

        logger.info("Customer uplift prediction request received")

        # Prepare input features (order must match training)
        input_features = [
            request.age,
            request.monthlyIncome,
            request.tenure,
            request.engagementScore,
            request.sessionTime,
            request.activityChange,
            request.churnRisk,
            request.appVisitsPerWeek,
            request.regionCode,
            request.totalClicks,
            request.customerRating,
            request.satisfactionTrend,
        ]

        feature_names = [f"f{i}" for i in range(len(input_features))]
        input_df = pd.DataFrame([input_features], columns=feature_names)

        # Predict probabilities
        p_treat = models.uplift_treated_model.predict_proba(input_df)[0, 1]
        p_control = models.uplift_control_model.predict_proba(input_df)[0, 1]

        uplift = p_treat - p_control
        decision = should_send_ad(uplift)

        logger.info(f"Uplift prediction completed: uplift={uplift:.4f}")

        return CustomerUpliftResponse(
            success=True,
            treated_probability=round(float(p_treat), 4),
            control_probability=round(float(p_control), 4),
            predicted_uplift=round(float(uplift), 4),
            decision=decision,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Customer uplift prediction error: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during uplift prediction",
        )
