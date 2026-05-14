from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any

from utils.model_loader import models
from utils.helpers import process_input_data, get_risk_level
from config.logging_config import logger

router = APIRouter()



@router.post(
    "/predict",
    status_code=status.HTTP_200_OK,
)
async def predict_heart_disease(request: Dict[str, Any]):
    """Predict heart disease risk (Flask-equivalent FastAPI version)"""
    try:
        if models.heart_disease_model is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Model not loaded",
            )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided",
            )

        logger.info("Heart disease prediction request received")

        # Extract model components
        model_data = models.heart_disease_model
        model = model_data["model"]
        imputer = model_data["imputer"]
        scaler = model_data["scaler"]
        encoder = model_data["encoder"]
        numeric_cols = model_data["numeric_cols"]
        categorical_cols = model_data["categorical_cols"]
        encoded_cols = model_data["encoded_cols"]

        # Preprocess input (same as Flask)
        processed_data = process_input_data(
            request,
            imputer,
            scaler,
            encoder,
            numeric_cols,
            categorical_cols,
            encoded_cols,
        )

        # Prediction
        prediction = int(model.predict(processed_data)[0])
        probability = model.predict_proba(processed_data)[0]

        logger.info(f"Heart disease prediction result: {prediction}")

        return {
            "success": True,
            "prediction": prediction,
            "prediction_label": (
                "Heart Disease Detected" if prediction == 1 else "No Heart Disease"
            ),
            "confidence": {
                "no_disease": round(float(probability[0]), 4),
                "disease": round(float(probability[1]), 4),
            },
            "risk_level": get_risk_level(probability[1]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Heart disease prediction error: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {str(e)}",
        )


# =========================
# Model Info Endpoint
# =========================

@router.get("/model-info")
async def model_info():
    """Get heart disease model info (Flask-equivalent)"""
    try:
        if models.heart_disease_model is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Model not loaded",
            )

        model_data = models.heart_disease_model

        return {
            "success": True,
            "model_type": "Logistic Regression",
            "numeric_features": model_data["numeric_cols"],
            "categorical_features": model_data["categorical_cols"],
            "total_features": len(model_data["numeric_cols"])
            + len(model_data["encoded_cols"]),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
