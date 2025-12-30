from flask import Flask, jsonify
from flask_cors import CORS
from config import DevelopmentConfig
import secrets
import os
from datetime import timedelta
import time

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://*.vercel.app",
            "https://deploy-five-khaki.vercel.app",
            "https://deploy-ten-orcin.vercel.app",
            "https://www.achintahazra.shop",
            "https://appsy-ivory.vercel.app"
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
from api.leaf_predict import predict_leaf_name

# --- Register Machine Learning blueprints ---
app.register_blueprint(predict_medical_charge, url_prefix='/medical-charge')
app.register_blueprint(prediction_heart_disease, url_prefix='/heart-disease')
app.register_blueprint(prediction_customer_churn, url_prefix='/customer-churn')
app.register_blueprint(predict_customer_uplift, url_prefix='/predict_uplift')
app.register_blueprint(backup_blueprint)
app.register_blueprint(predict_leaf_name)

@app.route('/')
def home():
    return {"message": "Machine Learning Models API", "version": "1.1.0"}

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "uptime": time.time(),
        "timestamp": int(time.time() * 1000)
    }), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)