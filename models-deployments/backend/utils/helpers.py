import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

def validate_age(age: int) -> bool:
    """Validate age input"""
    return 18 <= age <= 100

def validate_bmi(bmi: float) -> bool:
    """Validate BMI input"""
    return 10 <= bmi <= 50

def validate_children(children: int) -> bool:
    """Validate children count"""
    return 0 <= children <= 10

def format_currency(amount: float) -> str:
    """Format amount as currency"""
    return f"${amount:,.2f}"

def get_risk_level(probability: float) -> str:
    """Determine risk level from probability"""
    if probability < 0.3:
        return 'Low'
    elif probability < 0.6:
        return 'Medium'
    else:
        return 'High'

def process_input_data(
    data: Dict[str, Any],
    imputer,
    scaler,
    encoder,
    numeric_cols: list,
    categorical_cols: list,
    encoded_cols: list
) -> pd.DataFrame:
    """
    Process input data through preprocessing pipeline
    
    Args:
        data: Raw input data
        imputer: Fitted imputer
        scaler: Fitted scaler
        encoder: Fitted encoder
        numeric_cols: List of numeric column names
        categorical_cols: List of categorical column names
        encoded_cols: List of encoded column names
    
    Returns:
        Processed DataFrame ready for prediction
    """
    try:
        # Create DataFrame
        input_df = pd.DataFrame([data])
        
        # Add missing numeric columns with NaN
        imputer_cols = imputer.feature_names_in_
        for col in imputer_cols:
            if col not in input_df.columns:
                input_df[col] = np.nan
        
        # Apply imputation
        input_df[imputer_cols] = imputer.transform(input_df[imputer_cols])
        
        # Apply scaling
        input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])
        
        # Apply encoding
        input_encoded = pd.get_dummies(input_df)
        
        # Ensure all required columns are present
        encoded_feature_names = numeric_cols + list(encoded_cols)
        for col in encoded_feature_names:
            if col not in input_encoded.columns:
                input_encoded[col] = 0
        
        # Select only training columns
        input_encoded = input_encoded[encoded_feature_names]
        
        return input_encoded
    
    except Exception as e:
        raise ValueError(f"Error processing input data: {str(e)}")