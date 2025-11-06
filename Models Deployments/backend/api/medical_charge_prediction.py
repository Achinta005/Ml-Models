from flask import Blueprint, request, jsonify
import pickle
import numpy as np
import os

predict_medical_charge = Blueprint('predict', __name__)

# Load models
model_path = os.path.join(os.path.dirname(__file__), '..', 'models')

try:
    with open(os.path.join(model_path, 'non_smoker_model.pkl'), 'rb') as f:
        non_smoker_model = pickle.load(f)
    
    with open(os.path.join(model_path, 'smoker_model.pkl'), 'rb') as f:
        smoker_model = pickle.load(f)
    
    print("Models loaded successfully :(1)smoker_model.pkl (2)non_smoker_model.pkl")
except Exception as e:
    print(f"✗ Error loading models: {e}")
    non_smoker_model = None
    smoker_model = None

@predict_medical_charge.route('/predict', methods=['POST'])
def predict():
    """Predict medical charges based on input data"""
    try:
        if not non_smoker_model or not smoker_model:
            return jsonify({"error": "Models not loaded"}), 500
        
        # Get JSON data
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['age', 'bmi', 'children', 'smoker', 'sex', 'region']
        if not all(field in data for field in required_fields):
            return jsonify({"error": f"Missing fields. Required: {required_fields}"}), 400
        
        # Extract and validate data
        try:
            age = float(data['age'])
            bmi = float(data['bmi'])
            children = int(data['children'])
            smoker = data['smoker'].lower()
            sex = data['sex'].lower()
            region = data['region'].lower()
        except (ValueError, TypeError) as e:
            return jsonify({"error": f"Invalid data type: {str(e)}"}), 400
        
        # Validate ranges
        if not (18 <= age <= 100):
            return jsonify({"error": "Age must be between 18 and 100"}), 400
        if not (10 <= bmi <= 50):
            return jsonify({"error": "BMI must be between 10 and 50"}), 400
        if not (0 <= children <= 10):
            return jsonify({"error": "Children must be between 0 and 10"}), 400
        
        # Convert categorical to numerical
        sex_bin = 1 if sex == 'male' else 0
        
        # One-hot encoding for region
        regions = ['northeast', 'northwest', 'southeast', 'southwest']
        if region not in regions:
            return jsonify({"error": f"Region must be one of: {regions}"}), 400
        region_encoded = [1 if r == region else 0 for r in regions]
        
        # Prepare input array
        input_features = [age, bmi, children, sex_bin] + region_encoded
        input_array = np.array([input_features])
        
        # Make prediction
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