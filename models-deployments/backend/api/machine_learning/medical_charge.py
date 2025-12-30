from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing import Literal
import numpy as np

from utils.model_loader import models
from utils.helpers import validate_age, validate_bmi, validate_children
from config.logging_config import logger

router = APIRouter()

class MedicalChargeRequest(BaseModel):
    age: int = Field(..., ge=18, le=100, description="Age between 18-100")
    bmi: float = Field(..., ge=10, le=50, description="BMI between 10-50")
    children: int = Field(..., ge=0, le=10, description="Number of children 0-10")
    smoker: Literal["yes", "no"] = Field(..., description="Smoking status")
    sex: Literal["male", "female"] = Field(..., description="Gender")
    region: Literal["northeast", "northwest", "southeast", "southwest"] = Field(..., description="Region")
    
    @validator('age')
    def validate_age_range(cls, v):
        if not validate_age(v):
            raise ValueError('Age must be between 18 and 100')
        return v
    
    @validator('bmi')
    def validate_bmi_range(cls, v):
        if not validate_bmi(v):
            raise ValueError('BMI must be between 10 and 50')
        return v
    
    @validator('children')
    def validate_children_range(cls, v):
        if not validate_children(v):
            raise ValueError('Children must be between 0 and 10')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "age": 35,
                "bmi": 25.5,
                "children": 2,
                "smoker": "no",
                "sex": "male",
                "region": "northeast"
            }
        }

class MedicalChargeResponse(BaseModel):
    success: bool
    predicted_charge: float
    input_data: dict

@router.post("/predict", response_model=MedicalChargeResponse, status_code=status.HTTP_200_OK)
async def predict_medical_charge(request: MedicalChargeRequest):
    """Predict medical charges based on input data"""
    try:
        # Check if models are loaded
        if not models.smoker_model or not models.non_smoker_model:
            logger.error("Models not loaded")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Models not loaded. Please contact administrator."
            )
        
        logger.info(f"Prediction request: age={request.age}, smoker={request.smoker}")
        
        # Convert categorical inputs
        sex_bin = 1 if request.sex == 'male' else 0
        
        # Encode region
        regions = ['northeast', 'northwest', 'southeast', 'southwest']
        region_encoded = [1 if r == request.region else 0 for r in regions]
        
        # Prepare input features
        input_features = [
            request.age,
            request.bmi,
            request.children,
            sex_bin
        ] + region_encoded
        
        input_array = np.array([input_features])
        
        # Make prediction
        if request.smoker == 'yes':
            prediction = models.smoker_model.predict(input_array)[0]
        else:
            prediction = models.non_smoker_model.predict(input_array)[0]
        
        logger.info(f"Prediction successful: {prediction:.2f}")
        
        return MedicalChargeResponse(
            success=True,
            predicted_charge=round(float(prediction), 2),
            input_data=request.dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {str(e)}"
        )

@router.get("/predict-info")
async def predict_info():
    """Get information about prediction endpoint"""
    return {
        "endpoint": "/medical-charge/predict",
        "method": "POST",
        "description": "Predict annual medical charges",
        "required_fields": {
            "age": "integer (18-100)",
            "bmi": "float (10-50)",
            "children": "integer (0-10)",
            "smoker": "string ('yes' or 'no')",
            "sex": "string ('male' or 'female')",
            "region": "string ('northeast', 'northwest', 'southeast', 'southwest')"
        },
        "example": {
            "age": 35,
            "bmi": 25.5,
            "children": 2,
            "smoker": "no",
            "sex": "male",
            "region": "northeast"
        }
    }