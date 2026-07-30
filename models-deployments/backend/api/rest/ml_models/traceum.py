from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import pandas as pd

from lib.utils.model_loader import get_traceum_models
from core.logger import logger

router = APIRouter()

class TraceumUpliftRequest(BaseModel):
    f0: float = 0.0
    f1: float = 0.0
    f2: float = 0.0
    f3: float = 0.0
    f4: float = 0.0
    f5: float = 0.0
    f6: float = 0.0
    f7: float = 0.0
    f8: float = 0.0
    f9: float = 0.0
    f10: float = 0.0
    f11: float = 0.0

class TraceumUpliftResponse(BaseModel):
    success: bool
    uplift_t: float
    uplift_s: float
    avg_uplift: float
    send_ad: bool

@router.post(
    "/predict",
    response_model=TraceumUpliftResponse,
    status_code=status.HTTP_200_OK,
)
async def predict_traceum_uplift(request: TraceumUpliftRequest):
    """Predict Traceum uplift via REST HTTP endpoint"""
    try:
        treated_model, control_model, s_model = get_traceum_models()

        if treated_model is None or control_model is None or s_model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Traceum models not loaded",
            )

        feature_cols = [f"f{i}" for i in range(12)]
        input_df = pd.DataFrame(
            [[
                request.f0, request.f1, request.f2, request.f3,
                request.f4, request.f5, request.f6, request.f7,
                request.f8, request.f9, request.f10, request.f11
            ]],
            columns=feature_cols,
        )

        p1_t: float = float(treated_model.predict_proba(input_df)[0, 1])
        p0_t: float = float(control_model.predict_proba(input_df)[0, 1])
        uplift_t = p1_t - p0_t

        input_t1 = input_df.copy()
        input_t1["treatment"] = 1
        input_t0 = input_df.copy()
        input_t0["treatment"] = 0

        p1_s: float = float(s_model.predict_proba(input_t1)[0, 1])
        p0_s: float = float(s_model.predict_proba(input_t0)[0, 1])
        uplift_s = p1_s - p0_s

        avg_uplift = (uplift_t + uplift_s) / 2

        return TraceumUpliftResponse(
            success=True,
            uplift_t=round(uplift_t, 4),
            uplift_s=round(uplift_s, 4),
            avg_uplift=round(avg_uplift, 4),
            send_ad=bool(avg_uplift > 0.01),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Traceum prediction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {str(e)}",
        )
