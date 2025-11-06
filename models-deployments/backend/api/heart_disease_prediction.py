from flask import Blueprint, request, jsonify
from utils.helpers2 import load_model, process_input_data
import os
import requests
import joblib

prediction_heart_disease = Blueprint('prediction', __name__)

# --- CONFIG ---
GOOGLE_DRIVE_ID = "1ERT2W7llbp-VJ-iCCvfsd_r3WUAl-S2V"
MODEL_URL = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_ID}"
LOCAL_MODEL_PATH = "models/Heart_Disease_Predictor.joblib"

# --- FUNCTION TO DOWNLOAD MODEL IF NEEDED ---
def download_model_if_needed(url, local_path):
    """Download model file from Google Drive if not cached."""
    if not os.path.exists(local_path):
        print("Downloading Heart Disease model from Google Drive...")
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print("Model downloaded successfully.")
        else:
            print(f"Error downloading model: status {response.status_code}")
            return None
    return local_path

# --- LOAD MODEL ONCE ---
download_model_if_needed(MODEL_URL, LOCAL_MODEL_PATH)
model_data = load_model(LOCAL_MODEL_PATH)

@prediction_heart_disease.route('/predict', methods=['POST'])
def predict():
    try:
        if model_data is None:
            return jsonify({'success': False, 'error': 'Model not loaded'}), 500

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Extract model components
        model = model_data['model']
        imputer = model_data['imputer']
        scaler = model_data['scaler']
        encoder = model_data['encoder']
        numeric_cols = model_data['numeric_cols']
        categorical_cols = model_data['categorical_cols']
        encoded_cols = model_data['encoded_cols']

        # Preprocess input
        processed_data = process_input_data(
            data, imputer, scaler, encoder, numeric_cols, categorical_cols, encoded_cols
        )

        # Prediction
        prediction = model.predict(processed_data)[0]
        probability = model.predict_proba(processed_data)[0]

        result = {
            'success': True,
            'prediction': int(prediction),
            'prediction_label': 'Heart Disease Detected' if prediction == 1 else 'No Heart Disease',
            'confidence': {
                'no_disease': round(float(probability[0]), 4),
                'disease': round(float(probability[1]), 4)
            },
            'risk_level': get_risk_level(probability[1])
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'success': False, 'error': f'Prediction error: {str(e)}'}), 500


@prediction_heart_disease.route('/model-info', methods=['GET'])
def model_info():
    try:
        if model_data is None:
            return jsonify({'success': False, 'error': 'Model not loaded'}), 500

        return jsonify({
            'success': True,
            'model_type': 'Logistic Regression',
            'numeric_features': model_data['numeric_cols'],
            'categorical_features': model_data['categorical_cols'],
            'total_features': len(model_data['numeric_cols']) + len(model_data['encoded_cols'])
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_risk_level(disease_probability):
    if disease_probability < 0.3:
        return 'Low'
    elif disease_probability < 0.6:
        return 'Medium'
    else:
        return 'High'
