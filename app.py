import streamlit as st
import pandas as pd
import os
from io import BytesIO

# Assuming parser.py is in the same directory or accessible in the Python path
try:
    from parser import parse_bank_statement
except ImportError:
    st.error("Failed to import 'parse_bank_statement' from parser.py. Make sure parser.py is in the correct location.")
    # Add a dummy function to prevent NameError later if import fails
    def parse_bank_statement(pdf_path):
        st.error("Parser function not available.")
        return None

# --- Streamlit App UI ---

st.set_page_config(layout="wide", page_title="Bank Statement Parser")

st.title("Bank Statement Parser 📊")

st.write("""
Upload your bank statement PDF (HDFC, Union Bank supported for now)
and get the transactions extracted into an Excel file.
""")

# --- File Upload ---
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# --- Temporary File Handling and Parsing ---
if uploaded_file is not None:
    # To read the file content with pdftotext (used in parser.py),
    # it needs to be saved temporarily to disk.
    temp_dir = "temp_files"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    temp_file_path = os.path.join(temp_dir, uploaded_file.name)

    try:
        # Save the uploaded file bytes to the temporary file path
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.info(f"Processing '{uploaded_file.name}'...")

        # --- Call the parser function ---
        # CORRECTED ARGUMENT NAME HERE: pdf_path instead of pdf_file
        parsed_df = parse_bank_statement(pdf_path=temp_file_path)
        # ---

        if parsed_df is not None and not parsed_df.empty:
            st.success("Parsing successful!")
            st.dataframe(parsed_df)

            # --- Download Button ---
            # Convert DataFrame to Excel in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                parsed_df.to_excel(writer, index=False, sheet_name='Transactions')
                # Optional: Adjust column widths
                worksheet = writer.sheets['Transactions']
                for idx, col in enumerate(parsed_df): # Loop through columns
                    series = parsed_df[col]
                    max_len = max((
                        series.astype(str).map(len).max(), # Len of largest item
                        len(str(series.name)) # Len of column name/header
                    )) + 1 # Adding a little extra space
                    worksheet.set_column(idx, idx, max_len) # Set column width

            excel_data = output.getvalue()

            # Prepare filename for download
            base_filename = os.path.splitext(uploaded_file.name)[0]
            download_filename = f"{base_filename}_transactions.xlsx"

            st.download_button(
                label="📥 Download Transactions as Excel",
                data=excel_data,
                file_name=download_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        elif parsed_df is not None and parsed_df.empty:
            st.warning("Parsing completed, but no transactions were extracted. Check if the PDF format is supported or if the statement contains transactions.")
        else:
            # Error messages are printed by the parser function itself
            st.error("Parsing failed. Check the console/logs for more details.")

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        import traceback
        st.text(traceback.format_exc()) # Show detailed error in the app

    finally:
        # --- Clean up the temporary file ---
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                # print(f"Removed temporary file: {temp_file_path}") # Debugging print
            except Exception as e:
                st.warning(f"Could not remove temporary file {temp_file_path}: {e}")
        # Optionally remove the temp directory if empty, but might be better to leave it
        # if os.path.exists(temp_dir) and not os.listdir(temp_dir):
        #     os.rmdir(temp_dir)

else:
    st.info("Upload a PDF file to begin.")

# --- Footer or additional info ---
st.markdown("---")
st.markdown("Developed with Streamlit and Python.")
