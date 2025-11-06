from flask import Blueprint, request, jsonify
import joblib
import numpy as np
import pandas as pd
import os

predict_customer_uplift = Blueprint('predict_customer_uplift', __name__)

# Load models from ../models directory
model_path = os.path.join(os.path.dirname(__file__), '..', 'models')

try:
    model_treated = joblib.load(os.path.join(model_path, 'uplift_t_model.pkl'))
    model_control = joblib.load(os.path.join(model_path, 'uplift_c_model.pkl'))
    print("✅ Models loaded successfully: (1) Treated  (2) Control")
except Exception as e:
    print(f"✗ Error loading uplift models: {e}")
    model_treated = None
    model_control = None


def should_send_ad(uplift_value: float, threshold: float = 0.01) -> str:
    """Determine whether to send an ad based on uplift value."""
    if uplift_value > threshold:
        return "Send Ad (user likely to respond positively)"
    elif uplift_value < -threshold:
        return "Do NOT send Ad (ad may reduce conversion)"
    else:
        return "Neutral - no significant effect"


@predict_customer_uplift.route('/predict', methods=['POST'])
def predict_uplift():
    """Predict uplift value and ad decision."""
    try:
        print("=" * 50)
        print("📥 Received POST request to /predict")

        # Check if models are available
        if model_treated is None or model_control is None:
            return jsonify({"error": "Models not loaded"}), 500

        # Parse JSON input
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

        # Convert input data safely
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

        # Match feature names used during training (f0 ... f11)
        feature_names = [f"f{i}" for i in range(len(input_features))]
        input_df = pd.DataFrame([input_features], columns=feature_names)

        # Predict probabilities for treated and control models
        p_treat = model_treated.predict_proba(input_df)[0, 1]
        p_control = model_control.predict_proba(input_df)[0, 1]
        uplift = p_treat - p_control
        decision = should_send_ad(uplift)

        print(f"✅ Prediction complete — Uplift: {uplift:.4f}")

        # Send JSON response
        return jsonify({
            "success": True,
            "treated_probability": round(float(p_treat), 4),
            "control_probability": round(float(p_control), 4),
            "predicted_uplift": round(float(uplift), 4),
            "decision": decision
        }), 200

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500
