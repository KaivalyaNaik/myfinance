import streamlit as st
import pandas as pd
import os
import traceback
import time

# Assuming parser.py and classifier.py are in the same directory or accessible
try:
    from parser import parse_bank_statement
    # Import classifier functions needed here? Maybe just check model existence?
    from classifier import MODEL_FILE # To check initial status
except ImportError as e:
    st.error(f"Failed to import necessary functions: {e}. Make sure parser.py and classifier.py are present.")
    # Define dummy function/variable
    def parse_bank_statement(pdf_path): st.error("Parser function not available."); return pd.DataFrame()
    MODEL_FILE = 'classification_model.joblib'


# --- Initialize Session State ---
# Use keys that are less likely to collide if combining apps later
if 'statement_analyzer_parsed_df' not in st.session_state:
    st.session_state.statement_analyzer_parsed_df = pd.DataFrame()
if 'statement_analyzer_original_desc_col' not in st.session_state:
     st.session_state.statement_analyzer_original_desc_col = None
if 'statement_analyzer_model_loaded' not in st.session_state:
    st.session_state.statement_analyzer_model_loaded = os.path.exists(MODEL_FILE)
# Use file name and size to track the current file, instead of non-existent id
if 'statement_analyzer_file_info' not in st.session_state:
     st.session_state.statement_analyzer_file_info = None # Stores (name, size) tuple


# --- Streamlit App UI ---
# Page config MUST be the first Streamlit command
st.set_page_config(layout="wide", page_title="Statement Upload")

st.title("Bank Statement Analyzer 🧠📊")
st.write("""
Upload your bank statement PDF (HDFC, Union Bank supported).
Once processed, navigate using the sidebar to:
* **View & Edit Transactions:** See detailed transactions and correct categories.
* **Classification Summary:** View spending summaries by category.
* **Manage Classifier:** Retrain the ML model with your corrections.
""")
st.info(f"Current Classifier Model Status: {'**Trained**' if st.session_state.statement_analyzer_model_loaded else '**Not Trained** (Needs Corrections & Retraining)'}")


# --- File Upload ---
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="main_uploader")

# --- Processing Logic ---
if uploaded_file is not None:
    current_file_info = (uploaded_file.name, uploaded_file.size)
    # Check if it's a new file or the same one re-uploaded
    # Compare current file info tuple with the one stored in session state
    new_file_uploaded = (current_file_info != st.session_state.get('statement_analyzer_file_info'))

    if new_file_uploaded:
        # Store new file info tuple in session state
        st.session_state.statement_analyzer_file_info = current_file_info
        st.info(f"Processing '{uploaded_file.name}'...")
        temp_dir = "temp_files"
        if not os.path.exists(temp_dir):
            try: os.makedirs(temp_dir)
            except OSError as e: st.error(f"Failed to create temp dir: {e}"); st.stop()
        # Use a combination of name and size for a more unique temp name (optional)
        temp_file_name = f"uploaded_{uploaded_file.name}_{uploaded_file.size}.pdf"
        # Sanitize filename if needed (remove invalid characters) - basic example
        temp_file_name = "".join(c for c in temp_file_name if c.isalnum() or c in ('_', '.', '-')).rstrip()
        temp_file_path = os.path.join(temp_dir, temp_file_name)


        try:
            with open(temp_file_path, "wb") as f: f.write(uploaded_file.getbuffer())

            # --- Call the parser function (includes ML classification) ---
            with st.spinner("Parsing PDF and classifying transactions..."):
                # Ensure parse_bank_statement returns cleaned column names
                parsed_df_cleaned = parse_bank_statement(pdf_path=temp_file_path)
            # ---

            if parsed_df_cleaned is not None and not parsed_df_cleaned.empty:
                st.success("File processed successfully!")
                # Store the processed DataFrame in session state
                st.session_state.statement_analyzer_parsed_df = parsed_df_cleaned

                # --- Determine and store original description column name ---
                # This part is tricky as cleaning happens in parse_bank_statement
                # We might need parse_bank_statement to return original names too,
                # or make assumptions based on cleaned names.
                # Assumption: If 'Remarks' (cleaned) exists, original was 'Remarks'. If 'Narration' exists, original was 'Narration'.
                if 'Remarks' in parsed_df_cleaned.columns:
                     st.session_state.statement_analyzer_original_desc_col = 'Remarks'
                elif 'Narration' in parsed_df_cleaned.columns:
                     st.session_state.statement_analyzer_original_desc_col = 'Narration'
                else:
                     # Try finding based on partial match if exact failed
                     orig_desc_guess = next((col for col in parsed_df_cleaned.columns if 'Remark' in col or 'Narrat' in col), None)
                     if orig_desc_guess:
                          # Need to map back to the most likely original name
                          st.session_state.statement_analyzer_original_desc_col = 'Remarks' if 'Remark' in orig_desc_guess else 'Narration'
                     else:
                          st.session_state.statement_analyzer_original_desc_col = None
                print(f"DEBUG APP: Determined original desc col: {st.session_state.statement_analyzer_original_desc_col}")
                # --- End Description Column Logic ---


                st.info("Navigate to other pages using the sidebar to view results.")
                # Trigger rerun to ensure other pages update immediately after processing
                # st.rerun() # Use this in newer Streamlit versions

            elif parsed_df_cleaned is not None and parsed_df_cleaned.empty:
                st.warning("Parsing completed, but no transactions were extracted.")
                st.session_state.statement_analyzer_parsed_df = pd.DataFrame() # Clear state
                st.session_state.statement_analyzer_original_desc_col = None
            else:
                st.error("Parsing failed. Check console logs.")
                st.session_state.statement_analyzer_parsed_df = pd.DataFrame() # Clear state
                st.session_state.statement_analyzer_original_desc_col = None

        except Exception as e:
            st.error(f"An unexpected error occurred during processing: {e}")
            st.text(traceback.format_exc())
            st.session_state.statement_analyzer_parsed_df = pd.DataFrame() # Clear state
            st.session_state.statement_analyzer_original_desc_col = None

        finally:
            # --- Clean up the temporary file ---
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except Exception as e: st.warning(f"Could not remove temp file: {e}")
    else:
         # File already uploaded and processed, show message
         st.info(f"'{uploaded_file.name}' already processed. Navigate pages using the sidebar.")


else:
    # Clear state if no file is uploaded
    if st.session_state.statement_analyzer_file_info is not None:
         print("DEBUG: Clearing session state as file is removed.")
         st.session_state.statement_analyzer_parsed_df = pd.DataFrame()
         st.session_state.statement_analyzer_original_desc_col = None
         st.session_state.statement_analyzer_file_info = None # Clear file info
    st.info("Upload a PDF file to begin.")


# --- Footer or additional info ---
st.markdown("---")
st.markdown("Developed with Streamlit and Python.")
