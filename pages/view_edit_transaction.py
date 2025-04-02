import streamlit as st
import pandas as pd
import os
import time
import csv
from io import BytesIO

# Assuming classifier.py is accessible from the parent directory
import sys
# Add parent directory to path to find classifier module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from classifier import save_corrections, CLASSIFICATION_RULES, CORRECTIONS_FILE
    AVAILABLE_CATEGORIES = list(CLASSIFICATION_RULES.keys())
except ImportError as e:
    st.error(f"Failed to import classifier functions: {e}")
    def save_corrections(corr_list, filename): st.error("Classifier function not available.")
    AVAILABLE_CATEGORIES = ['Uncategorized']
    CORRECTIONS_FILE = 'user_corrections.csv'


st.set_page_config(layout="wide", page_title="View/Edit Transactions")

st.title("View & Edit Transactions")
st.write("Review the parsed transactions below. You can edit the 'Category' column.")

# --- Check if data exists in session state ---
if 'statement_analyzer_parsed_df' not in st.session_state or st.session_state.statement_analyzer_parsed_df.empty:
    st.warning("No data loaded. Please upload a statement on the main 'app.py' page first.")
    st.stop() # Stop execution of this page

# --- Initialize edited DF state if needed ---
# Use a separate key for the edited state on this page
if 'view_edit_edited_df' not in st.session_state or st.session_state.get('statement_analyzer_file_id') != st.session_state.get('view_edit_file_id'):
    st.session_state.view_edit_edited_df = st.session_state.statement_analyzer_parsed_df.copy()
    st.session_state.view_edit_file_id = st.session_state.get('statement_analyzer_file_id') # Track which file this edit state belongs to


# --- Find relevant columns ---
df_to_edit = st.session_state.view_edit_edited_df
actual_category_col = next((col for col in df_to_edit.columns if col.upper() == 'CATEGORY'), None)
original_desc_col = st.session_state.get('statement_analyzer_original_desc_col', None) # Get original name stored from app.py

if actual_category_col:
    st.info("💡 Edit categories directly in the table below. Click the 'Save Category Changes' button to teach the classifier.")

    # Configure the category column as a selectbox
    column_config = {
        actual_category_col: st.column_config.SelectboxColumn(
            f"Edit {actual_category_col}",
            options=AVAILABLE_CATEGORIES,
            required=True,
        )
    }

    # Display the data editor
    edited_data = st.data_editor(
        df_to_edit, # Use the specific state for this page
        column_config=column_config,
        key=f"data_editor_view_edit_{st.session_state.view_edit_file_id}", # Key tied to file ID
        num_rows="dynamic", # Or "fixed" if you don't want row changes
        use_container_width=True,
        height=600 # Set a height for scrollability
    )

    # --- IMPORTANT: Update the session state with the edited data ---
    st.session_state.view_edit_edited_df = edited_data

    # --- Save Changes Button ---
    if st.button("💾 Save Category Changes"):
        if original_desc_col is None:
             st.error("Cannot save corrections: Original description column name was not determined during parsing.")
        else:
            changes_to_save = []
            # Compare initial parsed DF with the current state of the editor for THIS PAGE
            initial_df = st.session_state.statement_analyzer_parsed_df # Original parsed data
            current_edited_df = st.session_state.view_edit_edited_df # Current editor state

            try:
                 # Ensure initial DF still has the original description column name
                 if original_desc_col not in initial_df.columns:
                      st.error(f"Original description column '{original_desc_col}' not found in initial data. Cannot save.")
                 else:
                    # Merge based on index to compare
                    initial_comp = initial_df[[original_desc_col, actual_category_col]].copy()
                    current_comp = current_edited_df[[actual_category_col]].copy()
                    current_comp.rename(columns={actual_category_col: f"{actual_category_col}_edited"}, inplace=True)
                    comparison_df = initial_comp.merge(current_comp, left_index=True, right_index=True, how='inner')

                    changed_df = comparison_df[comparison_df[actual_category_col] != comparison_df[f'{actual_category_col}_edited']]

                    if not changed_df.empty:
                        for index, row in changed_df.iterrows():
                            description = row[original_desc_col]
                            if pd.notna(description):
                                changes_to_save.append({
                                    "Description": description,
                                    "Original_Category": row[actual_category_col],
                                    "Corrected_Category": row[f'{actual_category_col}_edited'],
                                    "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                                })
                            else: print(f"Skipping row index {index}: Invalid description.")

                        if changes_to_save:
                            save_corrections(changes_to_save, CORRECTIONS_FILE)
                            st.success(f"Saved {len(changes_to_save)} category changes! Use 'Manage Classifier' page to retrain.")
                            # Update the initial DF state to reflect saved changes? Or require retraining?
                            # Let's require retraining for simplicity.
                        else: st.info("No valid changes detected to save.")
                    else: st.info("No changes detected in categories to save.")
            except Exception as merge_ex:
                 st.error(f"Error comparing changes: {merge_ex}")


    # --- Download Button (for the CURRENTLY EDITED data) ---
    if not edited_data.empty: # Use the direct output of data_editor here
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            edited_data.to_excel(writer, index=False, sheet_name='Transactions')
            worksheet = writer.sheets['Transactions']; worksheet.autofit()
        excel_data = output.getvalue()
        # Use file ID from session state for unique download name
        file_id = st.session_state.get('statement_analyzer_file_id', 'current')
        download_filename = f"edited_transactions_{file_id}.xlsx"
        st.download_button(
            label="📥 Download Current View as Excel",
            data=excel_data, file_name=download_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.warning("Category column not found in the loaded data. Cannot enable editing.")
    # Display the raw data from session state if category column missing
    st.dataframe(st.session_state.statement_analyzer_parsed_df)

