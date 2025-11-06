from flask import Blueprint, request, jsonify
import joblib
import pandas as pd

# Blueprint
prediction_customer_churn = Blueprint('prediction_churn', __name__)

# Load model package (all components)
MODEL_PATH = 'models/customer_churn_prediction.joblib'

try:
    model_package = joblib.load(MODEL_PATH)
    model = model_package['model']
    imputer_num = model_package['imputer_num']
    imputer_cat = model_package['imputer_cat']
    scaler = model_package['scaler']
    encoder = model_package['encoder']
    numerical_cols = model_package['numerical_cols']
    categorical_cols = model_package['categorical_cols']
    encoded_cols = model_package['encoded_cols']
except Exception as e:
    model_package = None
    print(f"Error loading model: {e}")


@prediction_customer_churn.route('/prediction', methods=['POST'])
def prediction_churn():
    """Predict Customer Churn"""
    try:
        if model_package is None:
            return jsonify({
                'success': False,
                'error': 'Model not loaded. Check if customer_churn_prediction.joblib exists.'
            }), 500

        # Get JSON data from request
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        # Convert to DataFrame
        input_df = pd.DataFrame([data])

        # Process numerical columns
        input_df[numerical_cols] = imputer_num.transform(input_df[numerical_cols])
        input_df[numerical_cols] = scaler.transform(input_df[numerical_cols])

        # Process categorical columns
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
        return jsonify({
            'success': False,
            'error': f'Prediction error: {str(e)}'
        }), 500


@prediction_customer_churn.route('/model-info', methods=['GET'])
def model_info():
    """Get information about the loaded model"""
    try:
        if model_package is None:
            return jsonify({
                'success': False,
                'error': 'Model not loaded'
            }), 500

        return jsonify({
            'success': True,
            'model_type': str(type(model)).split("'")[1],
            'numeric_features': numerical_cols,
            'categorical_features': categorical_cols,
            'encoded_features': encoded_cols,
            'total_features': len(numerical_cols) + len(encoded_cols)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_risk_level(churn_probability):
    """Determine churn risk level"""
    if churn_probability < 0.3:
        return 'Low'
    elif churn_probability < 0.6:
        return 'Medium'
    else:
        return 'High'
