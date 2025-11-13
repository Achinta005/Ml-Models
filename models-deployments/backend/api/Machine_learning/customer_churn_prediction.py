from flask import Blueprint, request, jsonify
from utils.helpers2 import load_model
import os
import requests
import pandas as pd

# --- BLUEPRINT ---
prediction_customer_churn = Blueprint('prediction_churn', __name__)

# --- CONFIG ---
GOOGLE_DRIVE_ID = "1K7_bUT2futcBchMb8MrTdUxyeFUVSCO4"
MODEL_URL = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_ID}"
LOCAL_MODEL_PATH = "models/customer_churn_prediction.joblib"

# --- FUNCTION TO DOWNLOAD MODEL IF NEEDED ---
def download_model_if_needed(url, local_path):
    """Download model file from Google Drive if not cached locally."""
    if not os.path.exists(local_path):
        print(f"⬇️ Downloading {os.path.basename(local_path)} from Google Drive...")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"✅ {os.path.basename(local_path)} downloaded successfully.")
        else:
            print(f"Error downloading model: status {response.status_code}")
            return None
    return local_path

# --- LOAD MODEL ONCE ---
download_model_if_needed(MODEL_URL, LOCAL_MODEL_PATH)
model_package = load_model(LOCAL_MODEL_PATH)

if model_package:
    model = model_package['model']
    imputer_num = model_package['imputer_num']
    imputer_cat = model_package['imputer_cat']
    scaler = model_package['scaler']
    encoder = model_package['encoder']
    numerical_cols = model_package['numerical_cols']
    categorical_cols = model_package['categorical_cols']
    encoded_cols = model_package['encoded_cols']
else:
    model = None


# --- ROUTES ---
@prediction_customer_churn.route('/prediction', methods=['POST'])
def prediction_churn():
    """Predict Customer Churn"""
    try:
        if model is None:
            return jsonify({
                'success': False,
                'error': 'Model not loaded. Check if customer_churn_prediction.joblib exists or Drive ID is valid.'
            }), 500

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Convert input JSON to DataFrame
        input_df = pd.DataFrame([data])

        # Handle missing numeric values and scale
        input_df[numerical_cols] = imputer_num.transform(input_df[numerical_cols])
        input_df[numerical_cols] = scaler.transform(input_df[numerical_cols])

        # Handle categorical encoding
        encoded_values = encoder.transform(input_df[categorical_cols])
        encoded_df = pd.DataFrame(encoded_values, columns=encoded_cols)
        input_df = pd.concat([input_df[numerical_cols], encoded_df], axis=1)

        # Make prediction
        prediction = model.predict(input_df)[0]
        probabilities = model.predict_proba(input_df)[0]

        result = {
            'success': True,
            'prediction': prediction,
            'prediction_label': 'Customer Will Churn' if prediction == 'Yes' else 'Customer Will Stay',
            'confidence': {
                'stay': round(float(probabilities[0]), 4),
                'churn': round(float(probabilities[1]), 4)
            },
            'risk_level': get_risk_level(probabilities[1])
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Prediction error: {str(e)}'}), 500
