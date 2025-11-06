from flask import Flask
from flask_cors import CORS
from config import DevelopmentConfig

# Create Flask app
app = Flask(__name__)

# Load configuration
app.config.from_object(DevelopmentConfig)

# Enable CORS
# Enable CORS for ALL routes from your Vercel domain
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "http://localhost:5000",
            "https://deploy-five-khaki.vercel.app",  # Your Vercel domain
            "https://*.vercel.app" , # All Vercel preview URLs
            "https://deploy-ten-orcin.vercel.app"
        ],
        "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Import API routes
from api.medical_charge_prediction import predict_medical_charge
app.register_blueprint(predict_medical_charge, url_prefix='/medical-charge')

from api.heart_disease_prediction import prediction_heart_disease
app.register_blueprint(prediction_heart_disease,url_prefix='/heart-disease')

from api.customer_churn_prediction import prediction_customer_churn
app.register_blueprint(prediction_customer_churn,url_prefix='/customer-churn')

from api.uplift_model import predict_customer_uplift
app.register_blueprint(predict_customer_uplift,url_prefix='/predict_uplift')

@app.route('/')
def home():
    return {
        "message": "Machine Learning Models Api",
        "version": "1.0.0",
        "endpoints": {
            "predict_medical_charge": "/medical-charge/predict",
            "prediction_heart_disease":"/heart-disease/predict",
            "prediction_customer_churn":"/customer-churn/prediction",
            "health": "/health"
        }
    }

@app.route('/health')
def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)