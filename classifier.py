# --- START OF FILE classifier.py ---

import re
import pandas as pd
import numpy as np

# --- CLASSIFICATION RULES ---

# Define categories and associated keywords/patterns (case-insensitive)
# Expand this list based on your specific transactions
CLASSIFICATION_RULES = {
    'Food & Dining': ['ZOMATO', 'SWIGGY', 'RESTAURANT', 'CAFE', 'FOOD', 'HOTEL', 'JALEBI', 'TEA VILL', 'KAKA HAL', 'RED CHUT', 'BASKIN R', 'EATCLUB', 'MEJWANI', 'MCDONALD'],
    'Travel': ['UBER', 'OLA', 'IRCTC', 'RAILWAY', 'FLIGHT', 'TICKET', 'CONFIRMTICKET', 'MERU', 'RAPIDO'],
    'Groceries': ['ZEPTO', 'BLINKIT', 'GROCERY', 'MART', 'SUPERMARKET', 'BIGBASKET', 'DMART', 'GROFERS', 'RATNADEEP', 'MORE SUPERMARKET'],
    'Shopping': ['MYNTRA', 'AMAZON', 'FLIPKART', 'SHOPCLUES', 'AJIO', 'SHOP', 'CLOTHING', 'CRED', 'MALL', 'LIFESTYLE', 'PANTALOONS', 'SHOPPERS STOP', 'NYKAA'],
    'Utilities': ['BILLPAY', 'ELECTRICITY', 'MOBILE', 'RECHARGE', 'AIRTEL', 'VODAFONE', 'JIO', 'GOOGLE PLAY', r'PAYTM.?POSTPAID', 'BSNL', 'GAS', 'WATER', 'BROADBAND', 'DTH'], # Added regex example
    'Salary/Income': ['SALARY', 'PUBMATIC', 'INCOME', 'STIPEND', 'COMMISSION', 'DIVIDEND'], # Also consider large credits
    'Transfers': ['NEFT', 'RTGS', 'IMPS', 'TRANSFER', 'PAYMENT FROM PHONE', r'UPI/?AB', r'UPI/?CR', 'FUND TRANSFER'], # Added regex for UPI types
    'Fees/Charges': ['SMS CHARGES', 'FEE', 'CHARGE', 'ANNUAL MAINT', 'AMC', 'BANK CHARGE'],
    'Entertainment': ['BOOKMYSHOW', 'PVR', 'NETFLIX', 'SPOTIFY', 'YOUTUBE', 'PRIME VIDEO', 'HOTSTAR', 'DISNEY', 'INOX', 'GAMING', 'ZEE5'],
    'Rent': ['RENT', 'HOUSING SOCIETY', 'MAINTENANCE', 'NOBROKER'],
    'Investment': ['ZERODHA', 'UPSTOX', 'GROWW', 'MUTUAL FUND', 'SIP', 'ICCLZR', 'SHARES', 'STOCKS', 'ETMONEY'],
    'Health/Medical': ['PHARMACY', 'HOSPITAL', 'DOCTOR', 'MEDICAL', 'APOLLO', 'S S HOSP', 'MEDPLUS', 'NETMEDS'],
    'Fuel': ['PETROL', 'DIESEL', 'FUEL', 'HP PETRO', 'INDIAN OIL', 'IOCL', 'BPCL', 'SHELL'],
    # Add more categories and keywords
}

# --- CLASSIFICATION FUNCTIONS ---

def classify_transaction(description):
    """Classifies a single transaction based on its description using keywords."""
    if not isinstance(description, str):
        return 'Uncategorized'

    # Convert description to lowercase once for efficiency
    description_lower = description.lower()

    for category, keywords in CLASSIFICATION_RULES.items():
        for keyword in keywords:
            # Use regex word boundary \b for more precise matching
            # Escape special regex characters in the keyword itself
            # Match case-insensitively (already handled by lowercasing)
            try:
                # Check if keyword itself contains regex patterns (like Utilities/Transfers)
                if any(c in keyword for c in r'.?+*^$()[]{}|\\'): # Simple check for regex chars
                     pattern = keyword.lower() # Assume keyword is already a pattern
                else:
                    # Treat as plain keyword, escape and add word boundaries
                    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'

                if re.search(pattern, description_lower):
                    return category
            except re.error as e:
                 print(f"Warning: Regex error for keyword '{keyword}' in category '{category}': {e}")
                 # Fallback to simple substring check if regex fails for the keyword
                 if keyword.lower() in description_lower:
                     print(f"Info: Falling back to substring check for keyword '{keyword}'.")
                     return category

    # Default if no keyword matches
    return 'Uncategorized'

def add_classification(df):
    """Adds a 'Category' column to the DataFrame based on Remarks/Narration."""
    if df.empty:
        print("DataFrame is empty, skipping classification.")
        return df

    # Determine the description column ('Remarks' for Union, 'Narration' for HDFC)
    # Use original column names before potential cleaning in parser.py
    description_col = None
    if 'Remarks' in df.columns: description_col = 'Remarks'
    elif 'Narration' in df.columns: description_col = 'Narration'
    # Add more potential original column names if needed

    if description_col:
        print(f"Classifying transactions based on column: '{description_col}'")
        # Ensure the column exists before applying
        if description_col in df.columns:
            df['Category'] = df[description_col].apply(classify_transaction)
        else:
             print(f"Warning: Identified description column '{description_col}' not found in DataFrame.")
             if 'Category' not in df.columns: df['Category'] = 'Uncategorized'


        # --- Fallback Classification for Large Credits ---
        # Identify potential income transactions that were uncategorized
        try:
            # Use original column names here as well, before cleaning
            type_col = 'Type' if 'Type' in df.columns else None
            amount_num_col = 'Amount_Num' if 'Amount_Num' in df.columns else None
            deposit_amt_col = 'Deposit Amt.' if 'Deposit Amt.' in df.columns else None # HDFC specific original name

            income_threshold = 5000 # Define a threshold for significant credits

            # Check if 'Category' column was actually added before trying to modify it
            if 'Category' in df.columns:
                if type_col and amount_num_col:
                    numeric_amount = pd.to_numeric(df[amount_num_col], errors='coerce')
                    df.loc[(df['Category'] == 'Uncategorized') &
                           (df[type_col] == 'Cr') &
                           (numeric_amount.notna()) &
                           (numeric_amount > income_threshold), 'Category'] = 'Salary/Income'
                elif deposit_amt_col: # HDFC case
                     numeric_deposit = pd.to_numeric(df[deposit_amt_col], errors='coerce')
                     df.loc[(df['Category'] == 'Uncategorized') &
                            (numeric_deposit.notna()) &
                            (numeric_deposit > income_threshold), 'Category'] = 'Salary/Income'
                else:
                    print("Info: Columns for income fallback classification (Type/Amount_Num or Deposit Amt.) not found.")
            else:
                 print("Warning: 'Category' column missing, skipping income fallback.")


        except Exception as e:
            print(f"Warning: Error during fallback income classification: {e}")

    else:
        print("Warning: Could not find 'Remarks' or 'Narration' column for classification.")
        if 'Category' not in df.columns:
             df['Category'] = 'Uncategorized'

    return df

# --- END OF FILE classifier.py ---
