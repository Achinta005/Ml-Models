from flask import Blueprint, request, jsonify
import joblib
import numpy as np
import pandas as pd
import os
import requests

predict_customer_uplift = Blueprint('predict_customer_uplift', __name__)

# --- CONFIG ---
# Google Drive file IDs (replace with yours if needed)
GOOGLE_DRIVE_ID_TREATED = "1Akl2p0P666rzOf2zGpNZQ9xioZ0ua-oV"
GOOGLE_DRIVE_ID_CONTROL = "1c8B9K0qDX2gN4kDPKgl1YmhVWvULK7-c"

# Create download URLs
TREATED_MODEL_URL = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_ID_TREATED}"
CONTROL_MODEL_URL = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_ID_CONTROL}"

# Local cache directory
TREATED_MODEL_PATH = "models/uplift_t_model.pkl"
CONTROL_MODEL_PATH = "models/uplift_c_model.pkl"


# --- FUNCTION TO DOWNLOAD MODEL IF NEEDED ---
def download_model_if_needed(url, local_path):
    """Download model file from Google Drive if not cached."""
    if not os.path.exists(local_path):
        print(f"⬇️ Downloading {os.path.basename(local_path)} from Google Drive...")
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"✅ {os.path.basename(local_path)} downloaded successfully.")
        else:
            print(f"✗ Error downloading {os.path.basename(local_path)} — status code: {response.status_code}")
            return None
    return local_path


# --- LOAD MODELS ---
try:
    download_model_if_needed(TREATED_MODEL_URL, TREATED_MODEL_PATH)
    download_model_if_needed(CONTROL_MODEL_URL, CONTROL_MODEL_PATH)

    model_treated = joblib.load(TREATED_MODEL_PATH)
    model_control = joblib.load(CONTROL_MODEL_PATH)
    print(f"✅ {TREATED_MODEL_PATH} and {CONTROL_MODEL_PATH} loaded successfully")
except Exception as e:
    print(f"✗ Error loading uplift models: {e}")
    model_treated = None
    model_control = None


# --- HELPER FUNCTION ---
def should_send_ad(uplift_value: float, threshold: float = 0.01) -> str:
    """Determine whether to send an ad based on uplift value."""
    if uplift_value > threshold:
        return "Send Ad (user likely to respond positively)"
    elif uplift_value < -threshold:
        return "Do NOT send Ad (ad may reduce conversion)"
    else:
        return "Neutral - no significant effect"


# --- PREDICTION ROUTE ---
@predict_customer_uplift.route('/predict', methods=['POST'])
def predict_uplift():
    """Predict uplift value and ad decision."""
    try:
        print("=" * 60)
        print("📥 Received POST request to /predict")

        # Check if models are available
        if model_treated is None or model_control is None:
            return jsonify({"error": "Models not loaded"}), 500

        # Parse input JSON
        data = request.get_json()
        required_fields = [
            'age', 'monthlyIncome', 'tenure', 'engagementScore',
            'sessionTime', 'activityChange', 'churnRisk', 'appVisitsPerWeek',
            'regionCode', 'totalClicks', 'customerRating', 'satisfactionTrend'
        ]

        if not all(field in data for field in required_fields):
            return jsonify({
                "error": f"Missing fields. Required: {required_fields}"
            }), 400

        # Validate and convert inputs
        try:
            input_features = [
                float(data['age']),
                float(data['monthlyIncome']),
                float(data['tenure']),
                float(data['engagementScore']),
                float(data['sessionTime']),
                float(data['activityChange']),
                float(data['churnRisk']),
                float(data['appVisitsPerWeek']),
                float(data['regionCode']),
                float(data['totalClicks']),
                float(data['customerRating']),
                float(data['satisfactionTrend'])
            ]
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"Invalid data type: {str(e)}"}), 400

        # Match training feature names
        feature_names = [f"f{i}" for i in range(len(input_features))]
        input_df = pd.DataFrame([input_features], columns=feature_names)

        # Predict uplift
        p_treat = model_treated.predict_proba(input_df)[0, 1]
        p_control = model_control.predict_proba(input_df)[0, 1]
        uplift = p_treat - p_control
        decision = should_send_ad(uplift)

        print(f"✅ Prediction complete — Uplift: {uplift:.4f}")

        return jsonify({
            "success": True,
            "treated_probability": round(float(p_treat), 4),
            "control_probability": round(float(p_control), 4),
            "predicted_uplift": round(float(uplift), 4),
            "decision": decision
        }), 200

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
