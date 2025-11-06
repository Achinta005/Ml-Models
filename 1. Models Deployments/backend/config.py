import os

class Config:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False