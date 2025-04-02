import streamlit as st
import pandas as pd
import os
import time
import sys # Keep sys import

# --- Use 'import classifier' style ---
try:
    # Add parent directory to path to find classifier module
    # This might still be needed depending on how Streamlit handles page execution context
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
        print(f"DEBUG ManageClassifier: Added {parent_dir} to sys.path")

    import classifier # Import the module itself
except ImportError as e:
    st.error(f"Failed to import classifier module: {e}. Ensure classifier.py exists in the parent directory.")
    # Define dummy functions/variables if import fails
    class ClassifierMock:
        CORRECTIONS_FILE = 'user_corrections.csv'
        MODEL_FILE = 'classification_model.joblib'
        MIN_SAMPLES_FOR_TRAINING = 10
        def train_classifier(self, df): st.error("Classifier function not available."); return None
        def load_raw_corrections_df(self, filename): return pd.DataFrame()
    classifier = ClassifierMock() # Use the mock object


st.set_page_config(layout="wide", page_title="Manage Classifier")

st.title("Manage Classifier Model")
st.write("Retrain the machine learning model using the latest saved category corrections.")

# --- Display Status ---
st.subheader("Status")
# Access constants via the imported module object
model_exists = os.path.exists(classifier.MODEL_FILE)
corrections_exist = os.path.exists(classifier.CORRECTIONS_FILE)

# Initialize session state if needed (might be set by app.py already)
if 'statement_analyzer_model_loaded' not in st.session_state:
     st.session_state.statement_analyzer_model_loaded = model_exists

st.write(f"**Model File:** `{classifier.MODEL_FILE}` ({'Exists' if model_exists else 'Not Found'})")
st.write(f"**Corrections File:** `{classifier.CORRECTIONS_FILE}` ({'Exists' if corrections_exist else 'Not Found'})")

num_corrections = 0
if corrections_exist:
     try:
          with open(classifier.CORRECTIONS_FILE, 'r', encoding='utf-8') as f:
               # Handle potential empty file or just header
               num_corrections = sum(1 for row in csv.reader(f))
               if num_corrections > 0: num_corrections -= 1 # Subtract header if rows exist
     except Exception as read_err:
          print(f"Error reading corrections file count: {read_err}")
          num_corrections = "Error reading"
st.write(f"**Number of Saved Corrections:** {num_corrections}")
st.write(f"*(Minimum required for training: {classifier.MIN_SAMPLES_FOR_TRAINING})*")


# --- Retraining Section ---
st.subheader("Retrain Model")

# Check conditions using module constants
if not corrections_exist:
     st.warning(f"Cannot retrain: Corrections file '{classifier.CORRECTIONS_FILE}' not found. Please save some corrections first.")
elif isinstance(num_corrections, int) and num_corrections < classifier.MIN_SAMPLES_FOR_TRAINING:
     st.warning(f"Cannot retrain: Insufficient corrections ({num_corrections}). Need at least {classifier.MIN_SAMPLES_FOR_TRAINING}. Please save more corrections.")
else:
    if st.button("🔄 Retrain Classifier Now"):
        with st.spinner("Loading corrections and retraining model... This may take a moment."):
            # Call functions via the imported module object
            corrections_df = classifier.load_raw_corrections_df()
            if not corrections_df.empty and len(corrections_df) >= classifier.MIN_SAMPLES_FOR_TRAINING:
                trained_pipeline = classifier.train_classifier(corrections_df)
                if trained_pipeline:
                    st.session_state.statement_analyzer_model_loaded = True
                    st.success("Classifier retrained successfully!")
                    st.info("The new model will be used the next time you upload a file.")
                    st.rerun() # Rerun page to update status display
                else:
                    st.error("Model training failed. Check console logs.")
                    st.session_state.statement_analyzer_model_loaded = False
            else:
                st.error(f"Loaded insufficient correction data ({len(corrections_df)} rows). Cannot retrain.")

