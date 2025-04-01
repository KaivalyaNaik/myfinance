import streamlit as st
import pandas as pd
import os
from io import BytesIO
import traceback # Import traceback for detailed error logging

# Assuming parser.py and classifier.py are in the same directory or accessible
try:
    # If using separate classifier.py:
    # from classifier import add_classification # Make sure classifier.py exists
    # from parser import parse_bank_statement # Assuming parse_bank_statement doesn't call add_classification internally anymore
    # If classification is still inside parser.py (as per parser_py_with_classifier artifact):
    from parser import parse_bank_statement
except ImportError as e:
    st.error(f"Failed to import necessary functions: {e}. Make sure parser.py (and classifier.py if used) are present.")
    # Define dummy function
    def parse_bank_statement(pdf_path):
        st.error("Parser function not available.")
        return pd.DataFrame() # Return empty DataFrame

# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="Bank Statement Analyzer")

st.title("Bank Statement Analyzer 📊")

st.write("""
Upload your bank statement PDF (HDFC, Union Bank supported).
Transactions will be extracted and classified. View all transactions or a classification summary in the tabs below.
""")

# --- File Upload ---
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# --- Temporary File Handling and Parsing ---
if uploaded_file is not None:
    temp_dir = "temp_files"
    if not os.path.exists(temp_dir):
        try:
            os.makedirs(temp_dir)
        except OSError as e:
            st.error(f"Failed to create temporary directory '{temp_dir}': {e}")
            st.stop()

    temp_file_path = os.path.join(temp_dir, "uploaded_statement.pdf")

    try:
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.info(f"Processing '{uploaded_file.name}'...")

        # --- Call the parser function ---
        # This function returns a DataFrame with cleaned column names including 'Category'
        parsed_df = parse_bank_statement(pdf_path=temp_file_path)
        # ---

        if parsed_df is not None and not parsed_df.empty:
            st.success("Parsing and Classification successful!")

            # --- Find Category and Amount Columns (using cleaned names) ---
            actual_category_col = next((col for col in parsed_df.columns if col.upper() == 'CATEGORY'), None)
            # Find a numeric amount column representing expenses (debits)
            expense_amount_col = None
            if 'Amount_Num' in parsed_df.columns and 'Type' in parsed_df.columns:
                 # Case for Union Bank/SBI derived columns
                 expense_amount_col = 'Amount_Num'
                 # We'll filter by Type == 'Dr' later
            elif 'Withdrawal_Amt' in parsed_df.columns:
                 # Case for HDFC (already represents debits)
                 expense_amount_col = 'Withdrawal_Amt'


            # --- Create Tabs ---
            tab1, tab2 = st.tabs(["All Transactions", "Classification Summary"])

            with tab1:
                st.header("All Transactions View")
                if actual_category_col:
                    st.subheader("Filter by Category")
                    all_categories = sorted(parsed_df[actual_category_col].unique())
                    selected_categories = st.multiselect(
                        "Select categories to display:",
                        options=all_categories,
                        default=all_categories # Show all by default
                    )

                    # Filter DataFrame based on selection
                    if selected_categories:
                        filtered_df = parsed_df[parsed_df[actual_category_col].isin(selected_categories)]
                    else:
                        filtered_df = pd.DataFrame(columns=parsed_df.columns) # Show empty if no categories selected

                    st.dataframe(filtered_df) # Display the filtered DataFrame

                    # --- Download Button (for the FILTERED data) ---
                    if not filtered_df.empty:
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            filtered_df.to_excel(writer, index=False, sheet_name='Transactions')
                            worksheet = writer.sheets['Transactions']
                            for idx, col in enumerate(filtered_df):
                                series = filtered_df[col]
                                max_len = max((series.astype(str).map(len).max(), len(str(series.name)))) + 1
                                worksheet.set_column(idx, idx, max_len)
                        excel_data = output.getvalue()
                        base_filename = os.path.splitext(uploaded_file.name)[0]
                        download_filename = f"{base_filename}_classified_transactions.xlsx"
                        st.download_button(
                            label="📥 Download Filtered Transactions as Excel",
                            data=excel_data, file_name=download_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.info("No transactions match the selected category filter.")

                else:
                    # If 'Category' column doesn't exist, just show the original DataFrame
                    st.warning("Category column not found in parsed data.")
                    st.dataframe(parsed_df)
                    # Download button for unclassified data
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        parsed_df.to_excel(writer, index=False, sheet_name='Transactions')
                        worksheet = writer.sheets['Transactions']
                        for idx, col in enumerate(parsed_df):
                            series = parsed_df[col]
                            max_len = max((series.astype(str).map(len).max(), len(str(series.name)))) + 1
                            worksheet.set_column(idx, idx, max_len)
                    excel_data = output.getvalue()
                    base_filename = os.path.splitext(uploaded_file.name)[0]
                    download_filename = f"{base_filename}_transactions_unclassified.xlsx"
                    st.download_button(
                        label="📥 Download Unclassified Transactions as Excel",
                        data=excel_data, file_name=download_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            with tab2:
                st.header("Classification Summary")
                if actual_category_col and expense_amount_col:
                    try:
                        # Ensure amount column is numeric
                        parsed_df[expense_amount_col] = pd.to_numeric(parsed_df[expense_amount_col], errors='coerce').fillna(0)

                        # Filter for expenses (Debits)
                        if 'Type' in parsed_df.columns: # Union/SBI case
                             expense_df = parsed_df[parsed_df['Type'] == 'Dr'].copy()
                        else: # HDFC case (Withdrawal_Amt already represents debits)
                             expense_df = parsed_df.copy()

                        # Group by category and sum the expense amount
                        summary = expense_df.groupby(actual_category_col)[expense_amount_col].agg(['sum', 'count']).reset_index()
                        summary.rename(columns={'sum': 'Total Amount', 'count': 'Transaction Count'}, inplace=True)
                        summary = summary.sort_values(by='Total Amount', ascending=False)

                        st.subheader("Expenses by Category")
                        st.dataframe(summary)

                        # --- Bar Chart ---
                        st.subheader("Spending Distribution")
                        # Prepare data for st.bar_chart (needs category as index)
                        chart_data = summary.set_index(actual_category_col)['Total Amount']
                        st.bar_chart(chart_data)

                    except Exception as e:
                        st.error(f"Could not generate classification summary: {e}")
                        st.text(traceback.format_exc())

                elif not actual_category_col:
                     st.warning("Category column not found. Cannot generate summary.")
                else: # Category found but not expense amount column
                     st.warning(f"Could not reliably identify expense amount column ('{expense_amount_col}' expected). Cannot generate summary.")


        elif parsed_df is not None and parsed_df.empty:
            st.warning("Parsing completed, but no transactions were extracted. Check if the PDF format is supported or if the statement contains transactions.")
        else:
            st.error("Parsing failed. Check the console/logs for more details.")

    except Exception as e:
        st.error(f"An unexpected error occurred in the application: {e}")
        st.text(traceback.format_exc())

    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                st.warning(f"Could not remove temporary file {temp_file_path}: {e}")

else:
    st.info("Upload a PDF file to begin.")

st.markdown("---")
st.markdown("Developed with Streamlit and Python.")
