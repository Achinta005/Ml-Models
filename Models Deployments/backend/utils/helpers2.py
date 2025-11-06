import joblib
import numpy as np
import pandas as pd
import os

def load_model(model_path):
    """
    Load the trained model and preprocessing objects from joblib file
    
    Args:
        model_path (str): Path to the joblib model file
    
    Returns:
        dict: Dictionary containing model and preprocessing objects, or None if failed
    """
    try:
        if not os.path.exists(model_path):
            print(f"Error: Model file not found at {model_path}")
            return None
        
        model_data = joblib.load(model_path)
        print(f"Model loaded successfully")
        return model_data
    
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None


def process_input_data(data, imputer, scaler, encoder, 
                      numeric_cols, categorical_cols, encoded_cols):
    """
    Process input data through all preprocessing steps
    
    Args:
        data (dict): Raw input data from frontend
        imputer: Fitted imputer for handling missing values
        scaler: Fitted scaler for feature scaling
        encoder: Fitted encoder for categorical variables
        numeric_cols (list): List of numeric column names
        categorical_cols (list): List of categorical column names
        encoded_cols (list): List of encoded column names
    
    Returns:
        pd.DataFrame: Processed data ready for model prediction
    """
    try:
        # Step 1: Create DataFrame from input data
        input_df = pd.DataFrame([data])
        
        # Step 2: Add missing numeric columns with NaN
        imputer_cols = imputer.feature_names_in_
        for col in imputer_cols:
            if col not in input_df.columns:
                input_df[col] = np.nan
        
        # Step 3: Apply imputation to handle missing values
        input_df[imputer_cols] = imputer.transform(input_df[imputer_cols])
        
        # Step 4: Apply scaling to numeric columns
        input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])
        
        # Step 5: Apply one-hot encoding for categorical columns
        input_encoded = pd.get_dummies(input_df)
        
        # Step 6: Ensure all required encoded columns are present
        encoded_feature_names = numeric_cols + list(encoded_cols)
        for col in encoded_feature_names:
            if col not in input_encoded.columns:
                input_encoded[col] = 0
        
        # Step 7: Select only the columns used during training
        input_encoded = input_encoded[encoded_feature_names]
        
        return input_encoded
    
    except Exception as e:
        print(f"Error processing input data: {str(e)}")
        raise


def validate_input_data(data, required_fields):
    """
    Validate if input data contains all required fields
    
    Args:
        data (dict): Input data to validate
        required_fields (list): List of required field names
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Input data must be a dictionary"
    
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, ""


def format_prediction_response(prediction, probability, prediction_label, risk_level):
    """
    Format the prediction response in a consistent structure
    
    Args:
        prediction (int): Prediction (0 or 1)
        probability (np.array): Probability array
        prediction_label (str): Human-readable prediction label
        risk_level (str): Risk level classification
    
    Returns:
        dict: Formatted response
    """
    return {
        'success': True,
        'prediction': int(prediction),
        'prediction_label': prediction_label,
        'confidence': {
            'no_disease': round(float(probability[0]), 4),
            'disease': round(float(probability[1]), 4)
        },
        'risk_level': risk_level
    }