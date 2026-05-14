from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Application settings"""
    
    # App Config
    APP_NAME: str = "ML Models API"
    VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Server Config
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # CORS Config
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://*.vercel.app",
        "https://deploy-five-khaki.vercel.app",
        "https://deploy-ten-orcin.vercel.app",
        "https://www.achintahazra.shop",
        "https://appsy-ivory.vercel.app"
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # or "text"
    
    # Model Paths
    MODELS_DIR: str = "models"
    
    # Google Drive IDs
    SMOKER_MODEL_ID: str = "1vhoNvvpkGJ6pYasbDFU7I_3lJcYtkqhh"
    NON_SMOKER_MODEL_ID: str = "173fNtLdFvlwPK5R1y0RB3doV5PX9nFbb"
    HEART_DISEASE_MODEL_ID: str = "1ERT2W7llbp-VJ-iCCvfsd_r3WUAl-S2V"
    CUSTOMER_CHURN_MODEL_ID: str = "1K7_bUT2futcBchMb8MrTdUxyeFUVSCO4"
    UPLIFT_TREATED_MODEL_ID: str = "1Akl2p0P666rzOf2zGpNZQ9xioZ0ua-oV"
    UPLIFT_CONTROL_MODEL_ID: str = "1c8B9K0qDX2gN4kDPKgl1YmhVWvULK7-c"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()