"""Utility functions"""

def validate_age(age):
    """Validate age input"""
    return 18 <= age <= 100

def validate_bmi(bmi):
    """Validate BMI input"""
    return 10 <= bmi <= 50

def validate_children(children):
    """Validate children count"""
    return 0 <= children <= 10

def format_currency(amount):
    """Format amount as currency"""
    return f"${amount:,.2f}"