import pickle
import joblib
import os
import requests
from typing import Optional
from config.logging_config import logger
from config.settings import settings

class ModelStore:
    """Global storage for loaded ML models"""
    smoker_model = None
    non_smoker_model = None
    heart_disease_model = None
    customer_churn_model = None
    uplift_treated_model =None
    uplift_control_model =None

models = ModelStore()

def download_model_if_needed(url: str, local_path: str) -> Optional[str]:
    """Download model file from Google Drive if not cached"""
    try:
        if os.path.exists(local_path):
            logger.info(f"Model already exists: {local_path}")
            return local_path
            
        logger.info(f"Downloading model to {local_path}")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Model downloaded successfully: {local_path}")
        return local_path
        
    except Exception as e:
        logger.error(f"Failed to download model: {str(e)}", exc_info=True)
        return None

def load_medical_charge_models():
    """Load medical charge prediction models"""
    try:
        SMOKER_URL = f"https://drive.google.com/uc?export=download&id={settings.SMOKER_MODEL_ID}"
        NON_SMOKER_URL = f"https://drive.google.com/uc?export=download&id={settings.NON_SMOKER_MODEL_ID}"
        
        SMOKER_PATH = f"{settings.MODELS_DIR}/smoker_model.pkl"
        NON_SMOKER_PATH = f"{settings.MODELS_DIR}/non_smoker_model.pkl"
        
        download_model_if_needed(SMOKER_URL, SMOKER_PATH)
        download_model_if_needed(NON_SMOKER_URL, NON_SMOKER_PATH)
        
        with open(SMOKER_PATH, 'rb') as f:
            models.smoker_model = pickle.load(f)
        with open(NON_SMOKER_PATH, 'rb') as f:
            models.non_smoker_model = pickle.load(f)
            
        logger.info("✅ Medical charge models loaded successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to load medical charge models: {str(e)}", exc_info=True)

def load_heart_disease_model():
    """Load heart disease prediction model"""
    try:
        MODEL_URL = f"https://drive.google.com/uc?export=download&id={settings.HEART_DISEASE_MODEL_ID}"
        LOCAL_PATH = f"{settings.MODELS_DIR}/Heart_Disease_Predictor.joblib"
        
        download_model_if_needed(MODEL_URL, LOCAL_PATH)
        models.heart_disease_model = joblib.load(LOCAL_PATH)
        logger.info("✅ Heart disease model loaded successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to load heart disease model: {str(e)}", exc_info=True)

def load_customer_churn_model():
    """Load customer churn prediction model"""
    try:
        MODEL_URL = f"https://drive.google.com/uc?export=download&id={settings.CUSTOMER_CHURN_MODEL_ID}"
        LOCAL_PATH = f"{settings.MODELS_DIR}/customer_churn_prediction.joblib"
        
        download_model_if_needed(MODEL_URL, LOCAL_PATH)
        models.customer_churn_model = joblib.load(LOCAL_PATH)
        logger.info("✅ Customer churn model loaded successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to load customer churn model: {str(e)}", exc_info=True)

def load_uplift_treated_model():
    """Load Uplift Treated Model"""
    try:
        MODEL_URL = f"https://drive.google.com/uc?export=download&id={settings.UPLIFT_TREATED_MODEL_ID}"
        LOCAL_PATH = f"{settings.MODELS_DIR}/uplift_treated_model.joblib"
        
        download_model_if_needed(MODEL_URL, LOCAL_PATH)
        models.uplift_treated_model = joblib.load(LOCAL_PATH)
        logger.info("✅ Uplift Treated model loaded successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to load uplift treated model: {str(e)}", exc_info=True)  
        

def load_uplift_control_model():
    """Load Uplift Control Model"""
    try:
        MODEL_URL = f"https://drive.google.com/uc?export=download&id={settings.UPLIFT_CONTROL_MODEL_ID}"
        LOCAL_PATH = f"{settings.MODELS_DIR}/uplift_control_model.joblib"
        
        download_model_if_needed(MODEL_URL, LOCAL_PATH)
        models.uplift_control_model = joblib.load(LOCAL_PATH)
        logger.info("✅ Uplift Control model loaded successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to load uplift control model: {str(e)}", exc_info=True)  
    
    
def load_all_models():
    """Load all models on startup"""
    logger.info("Loading all models...")
    load_medical_charge_models()
    load_heart_disease_model()
    load_customer_churn_model()
    load_uplift_treated_model()
    load_uplift_control_model()
    logger.info("Model loading complete!")