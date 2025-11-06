from flask import Blueprint, request, jsonify
import pickle
import numpy as np
import os
import requests

predict_medical_charge = Blueprint('predict', __name__)

# --- CONFIG ---
# Replace these with your actual Google Drive file IDs
GOOGLE_DRIVE_ID_SMOKER = "1vhoNvvpkGJ6pYasbDFU7I_3lJcYtkqhh"
GOOGLE_DRIVE_ID_NON_SMOKER = "173fNtLdFvlwPK5R1y0RB3doV5PX9nFbb"

MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', 'models')
SMOKER_MODEL_PATH = os.path.join(MODEL_DIR, 'smoker_model.pkl')
NON_SMOKER_MODEL_PATH = os.path.join(MODEL_DIR, 'non_smoker_model.pkl')

SMOKER_MODEL_URL = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_ID_SMOKER}"
NON_SMOKER_MODEL_URL = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_ID_NON_SMOKER}"


# --- FUNCTION TO DOWNLOAD MODEL IF NEEDED ---
def download_model_if_needed(url, local_path):
    """Download model file from Google Drive if not cached."""
    if not os.path.exists(local_path):
        print(f"Downloading {os.path.basename(local_path)} from Google Drive...")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"{os.path.basename(local_path)} downloaded successfully.")
        else:
            print(f"Error downloading model: {response.status_code}")
            return None
    return local_path


# --- LOAD MODELS ---
try:
    download_model_if_needed(NON_SMOKER_MODEL_URL, NON_SMOKER_MODEL_PATH)
    download_model_if_needed(SMOKER_MODEL_URL, SMOKER_MODEL_PATH)

    with open(NON_SMOKER_MODEL_PATH, 'rb') as f:
        non_smoker_model = pickle.load(f)
    with open(SMOKER_MODEL_PATH, 'rb') as f:
        smoker_model = pickle.load(f)

    print("✅ Models loaded successfully: (1) non_smoker_model.pkl, (2) smoker_model.pkl")

except Exception as e:
    print(f"✗ Error loading models: {e}")
    non_smoker_model = None
    smoker_model = None


# --- PREDICTION ROUTE ---
@predict_medical_charge.route('/predict', methods=['POST'])
def predict():
    """Predict medical charges based on input data"""
    try:
        if not non_smoker_model or not smoker_model:
            return jsonify({"error": "Models not loaded"}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        required_fields = ['age', 'bmi', 'children', 'smoker', 'sex', 'region']
        if not all(field in data for field in required_fields):
            return jsonify({"error": f"Missing fields. Required: {required_fields}"}), 400

        # Parse and validate input
        try:
            age = float(data['age'])
            bmi = float(data['bmi'])
            children = int(data['children'])
            smoker = data['smoker'].lower()
            sex = data['sex'].lower()
            region = data['region'].lower()
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"Invalid data type: {str(e)}"}), 400

        if not (18 <= age <= 100):
            return jsonify({"error": "Age must be between 18 and 100"}), 400
        if not (10 <= bmi <= 50):
            return jsonify({"error": "BMI must be between 10 and 50"}), 400
        if not (0 <= children <= 10):
            return jsonify({"error": "Children must be between 0 and 10"}), 400

        # Convert categorical inputs
        sex_bin = 1 if sex == 'male' else 0

        regions = ['northeast', 'northwest', 'southeast', 'southwest']
        if region not in regions:
            return jsonify({"error": f"Region must be one of: {regions}"}), 400

        region_encoded = [1 if r == region else 0 for r in regions]

        # Prepare input
        input_features = [age, bmi, children, sex_bin] + region_encoded
        input_array = np.array([input_features])

        # Prediction
        if smoker == 'yes':
            prediction = smoker_model.predict(input_array)[0]
        elif smoker == 'no':
            prediction = non_smoker_model.predict(input_array)[0]
        else:
            return jsonify({"error": "Smoker must be 'yes' or 'no'"}), 400

        return jsonify({
            "success": True,
            "predicted_charge": round(prediction, 2),
            "input_data": {
                "age": age,
                "bmi": bmi,
                "children": children,
                "smoker": smoker,
                "sex": sex,
                "region": region
            }
        }), 200

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- INFO ROUTE ---
@predict_medical_charge.route('/predict-info', methods=['GET'])
def predict_info():
    """Get information about prediction endpoint"""
    return jsonify({
        "endpoint": "/api/predict",
        "method": "POST",
        "description": "Predict annual medical charges",
        "required_fields": {
            "age": "integer (18-100)",
            "bmi": "float (10-50)",
            "children": "integer (0-10)",
            "smoker": "string ('yes' or 'no')",
            "sex": "string ('male' or 'female')",
            "region": "string ('northeast', 'northwest', 'southeast', 'southwest')"
        },
        "example": {
            "age": 35,
            "bmi": 25.5,
            "children": 2,
            "smoker": "no",
            "sex": "male",
            "region": "northeast"
        }
    })
