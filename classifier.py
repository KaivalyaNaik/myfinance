# --- START OF FILE classifier.py ---

import re
import pandas as pd
import numpy as np
import os
import csv
import joblib # For saving/loading model and vectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split # Optional: for evaluation
from sklearn.metrics import classification_report # Optional: for evaluation
import traceback # Ensure traceback is imported for error handling

# --- Configuration ---
CORRECTIONS_FILE = 'user_corrections.csv' # File with user overrides (training data)
MODEL_FILE = 'classification_model.joblib' # Saved ML model pipeline
MIN_SAMPLES_FOR_TRAINING = 10 # Minimum corrections needed to train a model

# --- CLASSIFICATION RULES (Initial/Fallback - Keep for reference/potential future use) ---
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
    'Uncategorized': [] # Ensure this exists for default/editing
}

# --- Correction Loading/Saving (Keep from previous version) ---

def load_raw_corrections_df(filename=CORRECTIONS_FILE):
    """Loads corrections data specifically for training."""
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename)
            if 'Description' in df.columns and 'Corrected_Category' in df.columns:
                 df.dropna(subset=['Description', 'Corrected_Category'], inplace=True)
                 df['Description'] = df['Description'].astype(str)
                 print(f"Loaded {len(df)} rows from corrections file for training.")
                 return df
            else:
                 print(f"Warning: Corrections file '{filename}' missing required columns. Cannot use for training.")
                 return pd.DataFrame()
        except Exception as e:
            print(f"Error loading corrections file '{filename}' for training: {e}")
            return pd.DataFrame()
    else:
        print(f"Corrections file '{filename}' not found. Cannot train model yet.")
        return pd.DataFrame()

def save_corrections(new_corrections_list, filename=CORRECTIONS_FILE):
    """Appends new corrections to the CSV file."""
    if not new_corrections_list: return
    file_exists = os.path.exists(filename)
    try:
        with open(filename, mode='a', newline='', encoding='utf-8') as csvfile:
            fieldnames = new_corrections_list[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists: writer.writeheader()
            writer.writerows(new_corrections_list)
        print(f"Saved {len(new_corrections_list)} new corrections to {filename}")
    except Exception as e:
        print(f"Error saving corrections to file '{filename}': {e}")

# --- ML Model Training and Loading ---

def train_classifier(data_df):
    """Trains and saves the classification pipeline (Vectorizer + Model)."""
    if data_df.empty or len(data_df) < MIN_SAMPLES_FOR_TRAINING:
        print(f"Insufficient data ({len(data_df)} rows) for training. Need at least {MIN_SAMPLES_FOR_TRAINING}.")
        if os.path.exists(MODEL_FILE):
             try: os.remove(MODEL_FILE); print(f"Removed existing model file {MODEL_FILE} due to insufficient training data.")
             except OSError as e: print(f"Error removing existing model file: {e}")
        return None
    print(f"Training classifier on {len(data_df)} samples...")
    X = data_df['Description'].str.lower()
    y = data_df['Corrected_Category']
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(stop_words='english', ngram_range=(1, 2))),
        ('clf', MultinomialNB(alpha=0.1)),
    ])
    try:
        pipeline.fit(X, y); print("Training complete.")
        joblib.dump(pipeline, MODEL_FILE); print(f"Classifier pipeline saved to {MODEL_FILE}")
        return pipeline
    except Exception as e:
        print(f"Error during classifier training or saving: {e}")
        traceback.print_exc(); return None

def load_classifier():
    """Loads the saved classification pipeline."""
    if os.path.exists(MODEL_FILE):
        try:
            pipeline = joblib.load(MODEL_FILE); print(f"Loaded classifier pipeline from {MODEL_FILE}")
            return pipeline
        except Exception as e: print(f"Error loading classifier pipeline from {MODEL_FILE}: {e}"); return None
    else: print(f"Model file '{MODEL_FILE}' not found. Train the model first."); return None

# --- Classification Function (using ML) ---

def classify_transaction_ml(description, pipeline):
    """Classifies a single transaction using the loaded ML pipeline."""
    if pipeline is None: return 'Uncategorized'
    if not isinstance(description, str) or not description.strip(): return 'Uncategorized'
    try:
        prediction = pipeline.predict([description.lower()])[0]; return prediction
    except Exception as e: print(f"Error during prediction for description '{description[:50]}...': {e}"); return 'Uncategorized'

def add_classification(df):
    """Adds/Updates a 'Category' column using the trained ML model."""
    if df.empty: print("DataFrame is empty, skipping classification."); return df
    pipeline = load_classifier()
    description_col = None
    if 'Remarks' in df.columns: description_col = 'Remarks'
    elif 'Narration' in df.columns: description_col = 'Narration'
    if description_col:
        print(f"Classifying transactions based on column: '{description_col}' using ML model...")
        if description_col in df.columns:
            df['Category'] = df[description_col].apply(lambda desc: classify_transaction_ml(desc, pipeline))
            print(f"ML classification applied. Sample categories: {df['Category'].value_counts().head()}")
        else:
             print(f"Warning: Identified description column '{description_col}' not found.")
             if 'Category' not in df.columns: df['Category'] = 'Uncategorized'
        # Fallback Classification for Large Credits
        try:
            type_col = 'Type' if 'Type' in df.columns else None
            amount_num_col = 'Amount_Num' if 'Amount_Num' in df.columns else None
            deposit_amt_col = 'Deposit Amt.' if 'Deposit Amt.' in df.columns else None
            income_threshold = 5000
            if 'Category' in df.columns:
                 if type_col and amount_num_col:
                     numeric_amount = pd.to_numeric(df[amount_num_col], errors='coerce')
                     df.loc[(df['Category'] == 'Uncategorized') & (df[type_col] == 'Cr') & (numeric_amount.notna()) & (numeric_amount > income_threshold), 'Category'] = 'Salary/Income'
                 elif deposit_amt_col:
                      numeric_deposit = pd.to_numeric(df[deposit_amt_col], errors='coerce')
                      df.loc[(df['Category'] == 'Uncategorized') & (numeric_deposit.notna()) & (numeric_deposit > income_threshold), 'Category'] = 'Salary/Income'
        except Exception as e: print(f"Warning: Error during fallback income classification: {e}")
    else:
        print("Warning: Could not find 'Remarks' or 'Narration' column for classification.")
        if 'Category' not in df.columns: df['Category'] = 'Uncategorized'
    print("Classification complete."); return df

# --- Add print statement at the end for import check ---
print("DEBUG: classifier.py module loaded successfully.")
# --- END OF FILE classifier.py ---
