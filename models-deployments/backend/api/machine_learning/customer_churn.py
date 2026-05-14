from fastapi import APIRouter, HTTPException, status
from typing import Dict
import pandas as pd

from utils.model_loader import models
from utils.helpers import get_risk_level
from config.logging_config import logger

router = APIRouter()


# =========================
# Prediction Endpoint
# =========================

@router.post(
    "/prediction",
    status_code=status.HTTP_200_OK,
)
async def predict_customer_churn(request: Dict):
    """Predict Customer Churn (Flask-equivalent FastAPI version)"""
    try:
        # Check model availability
        if models.customer_churn_model is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Model not loaded. Check model_loader configuration.",
            )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided",
            )

        logger.info("Customer churn prediction request received")

        # Extract model components
        model_data = models.customer_churn_model
        model = model_data["model"]
        imputer_num = model_data["imputer_num"]
        imputer_cat = model_data["imputer_cat"]
        scaler = model_data["scaler"]
        encoder = model_data["encoder"]
        numerical_cols = model_data["numerical_cols"]
        categorical_cols = model_data["categorical_cols"]
        encoded_cols = model_data["encoded_cols"]

        # Convert input JSON → DataFrame (same as Flask)
        input_df = pd.DataFrame([request])

        # Validate required columns dynamically
        missing_cols = set(numerical_cols + categorical_cols) - set(input_df.columns)
        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {list(missing_cols)}",
            )

        # Numerical preprocessing
        input_df[numerical_cols] = imputer_num.transform(input_df[numerical_cols])
        input_df[numerical_cols] = scaler.transform(input_df[numerical_cols])

        # Categorical preprocessing
        encoded_values = encoder.transform(input_df[categorical_cols])
        encoded_df = pd.DataFrame(encoded_values, columns=encoded_cols)

        # Final feature set
        final_df = pd.concat(
            [input_df[numerical_cols], encoded_df],
            axis=1,
        )

        # Prediction
        prediction = model.predict(final_df)[0]
        probabilities = model.predict_proba(final_df)[0]

        logger.info(f"Customer churn prediction result: {prediction}")

        return {
            "success": True,
            "prediction": prediction,
            "prediction_label": (
                "Customer Will Churn" if prediction == "Yes" else "Customer Will Stay"
            ),
            "confidence": {
                "stay": round(float(probabilities[0]), 4),
                "churn": round(float(probabilities[1]), 4),
            },
            "risk_level": get_risk_level(probabilities[1]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Customer churn prediction error: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {str(e)}",
        )
