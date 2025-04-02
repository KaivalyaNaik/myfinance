import streamlit as st
import pandas as pd
import os
import traceback

# Add parent directory to path to potentially find classifier module if needed
# (Though this page primarily reads session state)
import sys
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

st.set_page_config(layout="wide", page_title="Classification Summary")

st.title("Classification Summary")
st.write("Summary of expenses based on the current categories assigned in the 'View & Edit Transactions' page.")

# --- Check if data exists in session state ---
# Use the EDITED data for the summary
if 'view_edit_edited_df' not in st.session_state or st.session_state.view_edit_edited_df.empty:
    st.warning("No data available or edited data is empty. Please upload a statement on the main page and view/edit transactions first.")
    st.stop()

summary_df = st.session_state.view_edit_edited_df

# --- Find relevant columns ---
actual_category_col = next((col for col in summary_df.columns if col.upper() == 'CATEGORY'), None)
expense_amount_col = next((col for col in summary_df.columns if col == 'Amount_Num' or 'Withdrawal' in col), None)
type_col = next((col for col in summary_df.columns if col == 'Type'), None)

# --- Generate Summary ---
if actual_category_col and expense_amount_col:
    try:
        summary_df[expense_amount_col] = pd.to_numeric(summary_df[expense_amount_col], errors='coerce').fillna(0)
        expense_df = pd.DataFrame(columns=summary_df.columns)

        # Filter for expenses
        if type_col: # Union/SBI case
             expense_df = summary_df[(summary_df[type_col] == 'Dr') & (summary_df[expense_amount_col] > 0)].copy()
        elif 'Withdrawal_Amt' in summary_df.columns: # HDFC case
             expense_df = summary_df[summary_df['Withdrawal_Amt'] > 0].copy()
        elif expense_amount_col in summary_df.columns: # Fallback
             if type_col:
                  expense_df = summary_df[(summary_df[type_col] == 'Dr') & (summary_df[expense_amount_col] > 0)].copy()
             else: expense_df = summary_df[summary_df[expense_amount_col] > 0].copy()

        if not expense_df.empty:
            summary = expense_df.groupby(actual_category_col)[expense_amount_col].agg(['sum', 'count']).reset_index()
            summary.rename(columns={'sum': 'Total Spent', 'count': 'Transaction Count'}, inplace=True)
            summary = summary.sort_values(by='Total Spent', ascending=False)

            st.subheader("Expenses by Category")
            summary_display = summary.copy()
            summary_display['Total Spent'] = summary_display['Total Spent'].map('{:,.2f}'.format)
            st.dataframe(summary_display, use_container_width=True)

            st.subheader("Spending Distribution")
            chart_data = summary.set_index(actual_category_col)['Total Spent']
            st.bar_chart(chart_data, use_container_width=True)
        else:
             st.info("No expense transactions found in the current data to summarize.")

    except Exception as e:
        st.error(f"Could not generate classification summary: {e}")
        st.text(traceback.format_exc())
else:
     st.warning("Category or Expense Amount column not found. Cannot generate summary.")

