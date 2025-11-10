from flask import Flask
from flask_cors import CORS
from config import DevelopmentConfig
import secrets
import os
from datetime import timedelta

# Create Flask app
app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

# Enable CORS
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://*.vercel.app",
            "https://deploy-five-khaki.vercel.app",
            "https://deploy-ten-orcin.vercel.app",
            "https://www.achintahazra.shop"
        ],
        "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("⚠️  WARNING: Using auto-generated SECRET_KEY. Set SECRET_KEY in .env for production!")

app.secret_key = SECRET_KEY

# Session configuration
app.config.update(
    SESSION_COOKIE_NAME='portfolio_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1)
)

print("=" * 60)
print("🔧 Flask Configuration:")
print(f"✅ SECRET_KEY configured: {bool(app.secret_key)}")
print(f"✅ SECRET_KEY length: {len(app.secret_key)}")
print(f"✅ Session cookie: {app.config['SESSION_COOKIE_NAME']}")
print("=" * 60)


# --- Machine Learning Routes ---
from api.Machine_learning.medical_charge_prediction import predict_medical_charge
from api.Machine_learning.heart_disease_prediction import prediction_heart_disease
from api.Machine_learning.customer_churn_prediction import prediction_customer_churn
from api.Machine_learning.uplift_model import predict_customer_uplift
from api.backup_DB.backup_all_db import backup_blueprint

# --- Register Machine Learning blueprints ---
app.register_blueprint(predict_medical_charge, url_prefix='/medical-charge')
app.register_blueprint(prediction_heart_disease, url_prefix='/heart-disease')
app.register_blueprint(prediction_customer_churn, url_prefix='/customer-churn')
app.register_blueprint(predict_customer_uplift, url_prefix='/predict_uplift')

# ---------------------- Portfolio Routes ------------------------------
# Admin
from api.Portfolio.Admin import Admin_blueprint
# Authentication
from api.Portfolio.Authentication import Authentication_blueprint
# AnimeList
from api.Portfolio.AnimeList import AnimeList_bp
# About
from api.Portfolio.About import About_blueprint
# Projects 
from api.Portfolio.Projectdata import projects_blueprint
# Blog 
from api.Portfolio.Blogdata import blog_blueprint
# Contact
from api.Portfolio.Contact import contact_bp
# -------------------- Register Portfolio blueprints ------------------------
# Admin
app.register_blueprint(Admin_blueprint)
# Authentication
app.register_blueprint(Authentication_blueprint)
# AnimeList
app.register_blueprint(AnimeList_bp)
# About 
app.register_blueprint(About_blueprint)
# Projects 
app.register_blueprint(projects_blueprint)
# Blog 
app.register_blueprint(blog_blueprint)
# Contact
app.register_blueprint(contact_bp)

app.register_blueprint(backup_blueprint)

@app.route('/')
def home():
    return {"message": "Machine Learning Models API with Portfolio", "version": "1.1.0"}

@app.route('/health')
def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
