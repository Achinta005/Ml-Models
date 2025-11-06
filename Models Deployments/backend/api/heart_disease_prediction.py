from flask import Blueprint, request, jsonify
from utils.helpers2 import load_model, process_input_data
import os

prediction_heart_disease = Blueprint('prediction', __name__)

# Load model once at startup
MODEL_PATH = 'models/Heart_Disease_Predictor.joblib'
model_data = load_model(MODEL_PATH)

@prediction_heart_disease.route('/predict', methods=['POST'])
def predict():
    """
    Predict heart disease from patient data
    
    Expected JSON format:
    {
        'Gender': 'Male',
        'Blood Pressure': 0.466667,
        'Cholesterol Level': 0.933333,
        ...
    }
    """
    try:
        if model_data is None:
            return jsonify({
                'success': False,
                'error': 'Model not loaded. Check if Heart_Disease_Predictor.joblib exists.'
            }), 500
        
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Extract model components
        model = model_data['model']
        imputer = model_data['imputer']
        scaler = model_data['scaler']
        encoder = model_data['encoder']
        numeric_cols = model_data['numeric_cols']
        categorical_cols = model_data['categorical_cols']
        encoded_cols = model_data['encoded_cols']
        
        # Process input data
        processed_data = process_input_data(
            data,
            imputer,
            scaler,
            encoder,
            numeric_cols,
            categorical_cols,
            encoded_cols
        )
        
        # Make prediction
        prediction = model.predict(processed_data)[0]
        probability = model.predict_proba(processed_data)[0]
        
        # Format response
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
        return jsonify({
            'success': False,
            'error': f'Prediction error: {str(e)}'
        }), 500


@prediction_heart_disease.route('/model-info', methods=['GET'])
def model_info():
    """Get information about the loaded model"""
    try:
        if model_data is None:
            return jsonify({
                'success': False,
                'error': 'Model not loaded'
            }), 500
        
        return jsonify({
            'success': True,
            'model_type': 'Logistic Regression',
            'numeric_features': model_data['numeric_cols'],
            'categorical_features': model_data['categorical_cols'],
            'total_features': len(model_data['numeric_cols']) + len(model_data['encoded_cols'])
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def get_risk_level(disease_probability):
    """Determine risk level based on probability"""
    if disease_probability < 0.3:
        return 'Low'
    elif disease_probability < 0.6:
        return 'Medium'
    else:
        return 'High'