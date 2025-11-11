from flask import Flask
from flask_cors import CORS
from config import DevelopmentConfig
import secrets
import os
from datetime import timedelta

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

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
        "allow_headers": ["Content-Type", "Authorization", "x-grant-key"],
        "supports_credentials": True
    }
})


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
from api.Portfolio.AdminIpManger import ip_routes
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
app.register_blueprint(ip_routes)
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
