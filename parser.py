# --- START OF FILE parser.py ---

import pdftotext
import re
import pandas as pd
import numpy as np
import openpyxl
# Removed unused imports: WordCloud, matplotlib, tempfile
import os
import importlib.util
import sys
import traceback # Added for debugging unexpected errors

# Check if constants directory exists, if not create it
constants_dir = os.path.join(os.path.dirname(__file__), 'constants')
if not os.path.exists(constants_dir):
    os.makedirs(constants_dir)
    # Create __init__.py to make it a proper package
    with open(os.path.join(constants_dir, '__init__.py'), 'w') as f:
        pass

# Create banks.py if it doesn't exist
banks_file = os.path.join(constants_dir, 'banks.py')
if not os.path.exists(banks_file):
    with open(banks_file, 'w') as f:
        f.write(r"""# Bank specific regex patterns

# SBI Bank patterns
SBI = {
    'name': 'State Bank of India',
    'header': r"(?i)S\.?\s*No.*Date.*Transaction\s+Id.*Remarks.*Amount.*Balance",
    'balance': r"^([\d,]+\.\d+\s*\(\w+\))",
    'transaction_pattern': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(S\d+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))\s+([\d,]+\.\d+\s*\(\w+\))(?:\s+.*)?$",
    'transaction_mapping': {
        'sr_no': 1,
        'date': 2,
        'transaction_id': 3,
        'remarks': 4,
        'amount': 5,
        'balance': 6
    },
    'transaction_start_pattern': r"^\d+",
    'column_mapping': {
        'sr_no': 'S.No',
        'date': 'Date',
        'transaction_id': 'Transaction Id',
        'remarks': 'Remarks',
        'amount': 'Amount(Rs.)',
        'balance': 'Balance'
    }
}

# HDFC Bank patterns
HDFC = {
    'name': 'HDFC Bank',
    # Stricter regex focusing on mandatory spaces between keywords and handling Chq./Ref.No.
    'header': r"(?i)^\s*Date\s+Narration\s+Chq\.\s*\/\s*Ref\.\s*No\.?\s+Value\s+Dt\s+Withdrawal\s+Amt\s+Deposit\s+Amt\s+Closing\s+Balance",
    'transaction_pattern': r'''^\s*(\d{2}/\d{2}/\d{2})          # Transaction Date
        \s+(.*?)                                     # Narration (non-greedy)
        \s+(\S+)                                     # Chq./Ref.No.
        \s+(\d{2}/\d{2}/\d{2})                        # Value Date
        \s+([\d,]+\.\d{2})                           # Withdrawal Amount
        \s+([\d,]+\.\d{2})                           # Deposit Amount
        \s+([\d,]+\.\d{2})                           # Closing Balance
        (?:\s+.*)?$''',
    'transaction_mapping': {
        'date': 1,
        'narration': 2,
        'chq_ref_no': 3,
        'value_date': 4,
        'withdrawal_amt': 5,
        'deposit_amt': 6,
        'closing_balance': 7
    },
    'transaction_start_pattern': r"^\d{2}/\d{2}/\d{2}",
    'column_mapping': {
        'date': 'Date',
        'narration': 'Narration',
        'chq_ref_no': 'Chq/Ref.No.',
        'value_date': 'Value Date',
        'withdrawal_amt': 'Withdrawal Amt.',
        'deposit_amt': 'Deposit Amt.',
        'closing_balance': 'Closing Balance'
    }
}

# Union Bank patterns
UNION = {
    'name': 'Union Bank of India',
    'header': r"(?i)S\.?\s*No.*Date.*Transaction\s+Id.*Remarks.*Amount.*Balance",
    'balance': r"^([\d,]+\.\d+\s*\(\w+\))",
    'transaction_pattern': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(S\d+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))\s+([\d,]+\.\d+\s*\(\w+\))(?:\s+.*)?$",
    'transaction_mapping': {
        'sr_no': 1,
        'date': 2,
        'transaction_id': 3,
        'remarks': 4,
        'amount': 5,
        'balance': 6
    },
    'transaction_start_pattern': r"^\d+",
    'column_mapping': {
        'sr_no': 'S.No',
        'date': 'Date',
        'transaction_id': 'Transaction Id',
        'remarks': 'Remarks',
        'amount': 'Amount(Rs.)',
        'balance': 'Balance'
    }
}

# Add more banks as needed

# Dictionary of supported banks
BANKS = {
    'SBI': SBI,
    'HDFC': HDFC,
    'UNION': UNION
}
""")

# Import the banks module
try:
    from constants.banks import BANKS
except ImportError:
    # Manual import if normal import fails
    spec = importlib.util.spec_from_file_location("banks", banks_file)
    banks_module = importlib.util.module_from_spec(spec)
    sys.modules["banks"] = banks_module
    spec.loader.exec_module(banks_module)
    BANKS = banks_module.BANKS


class BankStatementParser:
    def __init__(self, bank_config=None):
        self.bank_config = bank_config

    def detect_bank(self, page_text):
        """Detect the bank based on the content of the page."""
        for bank_key, bank_config in BANKS.items():
            # Check for name first (more reliable if present)
            if bank_config['name'].lower() in page_text.lower():
                return bank_key

        # Try to detect based on header pattern if name not found
        for bank_key, bank_config in BANKS.items():
            # Use find_header to check if the pattern matches anywhere
            if self.find_header(page_text, config_override=bank_config):
                 print(f"DEBUG: Detected bank '{bank_config['name']}' via header pattern during detection.")
                 return bank_key

        print("DEBUG: Bank detection failed based on name and header patterns.")
        return None

    # Added config_override for use during detection phase
    def find_header(self, page_text, config_override=None):
        """Find the header row in the page text using the bank's header pattern."""
        active_config = config_override if config_override else self.bank_config

        if not active_config:
            print("DEBUG: find_header called but no active_config.")
            return None

        header_pattern = active_config['header']

        # --- START DEBUG ---
        if not config_override: # Only print detailed debug when actually parsing, not detecting
            print("-" * 20)
            print("DEBUG: Attempting to find header...")
            print(f"DEBUG: Using Bank: {active_config.get('name', 'Unknown')}")
            print(f"DEBUG: Regex Pattern: {header_pattern}")
            print("DEBUG: Searching within text (first ~500 chars):")
            print(page_text[:500])
            print("="*30)
            print("DEBUG: Full text for header search:")
            print(page_text) # Print the full text being searched
            print("="*30)
        # --- END DEBUG ---

        # Search line by line for a more robust match
        header_match_object = None
        matched_line_text = None
        for line in page_text.splitlines():
            # Strip leading/trailing whitespace from line before matching
            line_stripped = line.strip()
            if not line_stripped: # Skip empty lines
                continue
            header_match_object = re.search(header_pattern, line_stripped)
            if header_match_object:
                matched_line_text = line_stripped # Store the line text that matched
                break # Found it

        # --- Debug search result ---
        if header_match_object:
             if not config_override: # Only print detailed debug when actually parsing
                print(f"DEBUG: +++ Header FOUND using line-by-line search.")
                print(f"DEBUG: Matched Line: '{matched_line_text}'") # Print the specific line
                print(f"DEBUG: Matched Text: '{header_match_object.group(0)}'")
                print("-" * 20)
             return header_match_object.group(0) # Return the actual matched header text
        else:
             if not config_override: # Only print detailed debug when actually parsing
                print("DEBUG: --- Header NOT FOUND using line-by-line search. ---")
                print("-" * 20)
             return None

    def parse_transaction_line(self, transaction_line):
        """Parse a transaction line based on the bank configuration."""
        if not self.bank_config:
            return None

        pattern = self.bank_config['transaction_pattern']
        mapping = self.bank_config['transaction_mapping']

        # Use re.VERBOSE flag for HDFC pattern implicitly due to multiline string literal
        match = re.match(pattern, transaction_line, re.VERBOSE if 'HDFC' in self.bank_config.get('name','') else 0)
        if match:
            result = {}
            for field, group_index in mapping.items():
                # Strip whitespace from extracted fields
                result[field] = match.group(group_index).strip()
            return result
        else:
            # Log lines that don't match the transaction pattern
            # print(f"Warning: Could not parse transaction line starting with: '{transaction_line[:70]}...'")
            return None

    def parse_all_transactions(self, header_index, lines):
        """Parse all transactions from the lines after the header, handling multi-line entries."""
        if not self.bank_config:
            return []

        # Start from the line immediately after the header
        transactions_lines_data = lines[header_index+1:]
        transactions = []
        current_transaction_lines = [] # Store lines for the current transaction

        start_pattern = self.bank_config['transaction_start_pattern']

        for line in transactions_lines_data:
            line_stripped = line.strip()
            if not line_stripped: # Skip empty lines
                continue

            # Check if line matches the start pattern
            if re.match(start_pattern, line_stripped):
                # If we have accumulated lines for a previous transaction, join and add them
                if current_transaction_lines:
                    transactions.append(" ".join(current_transaction_lines))

                # Start a new transaction
                current_transaction_lines = [line_stripped]
            else:
                # Append to the current transaction (handles multi-line remarks/narration)
                # Only append if current_transaction_lines is not empty (avoid appending before first match)
                if current_transaction_lines:
                    current_transaction_lines.append(line_stripped)

        # Add the last transaction found
        if current_transaction_lines:
            transactions.append(" ".join(current_transaction_lines))

        return transactions

    def parse_transactions(self, transactions_text_list):
        """Parse a list of transaction lines (potentially multi-line joined) into a DataFrame."""
        parsed_transactions = []
        for transaction_text in transactions_text_list:
            parsed = self.parse_transaction_line(transaction_text)
            if parsed:
                parsed_transactions.append(parsed)
            else:
                 # Log the transaction text that failed parsing for easier debugging
                 print(f"Failed to parse transaction text block: '{transaction_text[:100]}...'")

        if not parsed_transactions:
             return pd.DataFrame() # Return empty DataFrame if nothing parsed

        df = pd.DataFrame(parsed_transactions)

        # --- START POST-PROCESSING for HDFC ---
        # Check if this is HDFC based on expected columns from the mapping used in parse_transaction_line
        if 'amounts_text' in df.columns and 'narration_part1' in df.columns:
            print("DEBUG: Running HDFC post-processing...")

            # --- 1. Combine Narration ---
            df['narration'] = df['narration_part1'].str.strip() + ' ' + df['narration_part2'].str.strip()
            df['narration'] = df['narration'].str.strip() # Clean up extra spaces

            # --- 2. Prepare Numeric Balance ---
            # Ensure closing_balance column exists before proceeding
            if 'closing_balance' not in df.columns:
                print("Error: 'closing_balance' column not found for HDFC post-processing.")
                # Fallback or return df as is? Let's drop temp columns and return
                df.drop(columns=['narration_part1', 'narration_part2', 'amounts_text'], inplace=True, errors='ignore')
                return df

            df['closing_balance_numeric'] = pd.to_numeric(
                df['closing_balance'].str.replace(',', '', regex=False), errors='coerce'
            )
            # Handle potential conversion errors if any balance wasn't purely numeric
            if df['closing_balance_numeric'].isnull().any():
                 print("Warning: Could not convert all closing balances to numeric. Amount assignment might be affected.")

            # --- 3. Calculate Balance Difference ---
            # Ensure the DataFrame is sorted chronologically if possible (assuming it mostly is)
            # HDFC statements are typically ordered correctly by pdftotext extraction
            df['balance_diff'] = df['closing_balance_numeric'].diff()

            # --- 4. Extract Amount Value ---
            amount_pattern = re.compile(r'([\d,]+\.\d{2})')
            # Apply search to the 'amounts_text' column
            extracted_matches = df['amounts_text'].apply(lambda x: amount_pattern.search(str(x)))
            # Store the extracted float amount temporarily
            df['temp_amount_float'] = 0.0
            for index, match in extracted_matches.items():
                 if match:
                     amount_str = match.group(1).replace(',', '')
                     try:
                         df.loc[index, 'temp_amount_float'] = float(amount_str)
                     except ValueError:
                          print(f"Warning: Could not convert extracted amount '{amount_str}' to float at index {index}")

            # --- 5. Assign Amounts to Correct Columns ---
            df['withdrawal_amt'] = 0.0
            df['deposit_amt'] = 0.0

            for index, row in df.iterrows():
                amount = row['temp_amount_float']
                diff = row['balance_diff']

                if amount == 0.0: # Skip if no amount was extracted
                    continue

                # Handle the first row (diff is NaN) - Make an educated guess or default
                if pd.isna(diff):
                    # Simple Default: Assume first transaction is withdrawal if uncertain
                    # A better approach might involve looking at an opening balance if available.
                    print(f"DEBUG: First row (Index {index}), assigning amount {amount} to Withdrawal (default).")
                    df.loc[index, 'withdrawal_amt'] = amount
                    continue

                # Check using numpy.isclose for floating point comparison
                # Tolerance (atol) might need adjustment based on data precision
                is_deposit = np.isclose(diff, amount, atol=0.01)
                is_withdrawal = np.isclose(diff, -amount, atol=0.01)

                if is_deposit:
                    df.loc[index, 'deposit_amt'] = amount
                elif is_withdrawal:
                    df.loc[index, 'withdrawal_amt'] = amount
                else:
                    # Amount doesn't match balance change (e.g., fees, interest, complex transactions)
                    print(f"Warning: Amount {amount} at index {index} doesn't match balance change {diff}. Assigning to Withdrawal (default).")
                    # Default assignment, could be refined
                    df.loc[index, 'withdrawal_amt'] = amount

            # --- 6. Clean Up Temporary Columns ---
            df.drop(columns=[
                'narration_part1', 'narration_part2', 'amounts_text',
                'closing_balance_numeric', 'balance_diff', 'temp_amount_float'
                ], inplace=True, errors='ignore') # errors='ignore' in case a column wasn't created

            # --- 7. Reorder columns for consistency (Optional but Recommended) ---
            final_columns = []
            original_mapping = self.bank_config.get('column_mapping', {})
            # Get the desired HDFC column names from the original mapping values
            desired_order = list(original_mapping.values())
            # Ensure all essential columns are present, add if missing from desired_order
            for col in ['date', 'narration', 'chq_ref_no', 'value_date', 'withdrawal_amt', 'deposit_amt', 'closing_balance']:
                 if col in df.columns:
                     final_columns.append(col)

            # Add any extra columns that might exist but weren't in mapping
            for col in df.columns:
                if col not in final_columns:
                    final_columns.append(col)
            try:
                 df = df[final_columns]
            except KeyError as e:
                 print(f"Warning: Could not reorder columns perfectly: {e}")


        # --- END POST-PROCESSING ---

        return df

    # Modified parse_page to accept an expect_header flag
    def parse_page(self, page_text, expect_header=True):
        """Parse a single page of the bank statement."""
        if not self.bank_config:
            print("Error: Bank configuration not set for parsing page.")
            return pd.DataFrame() # Return empty DataFrame on error

        header_index = -1
        lines = page_text.splitlines()
        actual_header_text_on_page = None

        # Find the header index robustly only if expected
        if expect_header:
            for i, line in enumerate(lines):
                # Use find_header method which uses the regex on stripped lines
                line_stripped = line.strip()
                if not line_stripped: continue
                header_match_text = self.find_header(line_stripped) # Pass stripped line
                if header_match_text:
                    header_index = i
                    actual_header_text_on_page = line_stripped # Capture the line text
                    print(f"DEBUG: Header index {header_index} found on page expected to have header.")
                    print(f"DEBUG: Actual Header Text Matched on Page: '{actual_header_text_on_page}'")
                    break
            if header_index == -1:
                print("DEBUG: Header NOT found on page where it was expected.")
                # Treat as non-fatal, maybe transactions start without header on this specific page?
                # Let's try parsing from the top anyway in this case.
                header_index = -1 # Try parsing from start of page
        else:
            # If header is not expected, start parsing from the beginning (index -1 means start at lines[0])
            print(f"DEBUG: Parsing all lines on subsequent page (header not expected).")
            header_index = -1 # Effectively start from the top

        transactions_data = self.parse_all_transactions(header_index, lines)
        df = self.parse_transactions(transactions_data)

        return df

    def parse_pdf(self, pdf_file, excel_file=None):
        """Parse a PDF bank statement and optionally save to Excel."""
        try:
            with open(pdf_file, "rb") as file:
                # Use default extraction mode (often equivalent to -layout)
                pdf = pdftotext.PDF(file)
                if not pdf:
                    print("Error: Could not read PDF or PDF is empty.")
                    return None
                first_page_text = pdf[0]

                # --- Auto-detect bank if not specified ---
                if not self.bank_config:
                    bank_key = self.detect_bank(first_page_text) # Use detect_bank method
                    if bank_key and bank_key in BANKS:
                        self.bank_config = BANKS[bank_key]
                        print(f"Detected bank: {self.bank_config['name']}")
                    else:
                        # Try page 2 for detection if available
                        if len(pdf) > 1:
                            bank_key = self.detect_bank(pdf[1])
                            if bank_key and bank_key in BANKS:
                                self.bank_config = BANKS[bank_key]
                                print(f"Detected bank (on page 2): {self.bank_config['name']}")

                        if not self.bank_config: # If still not detected
                             print("Error: Could not detect bank from PDF content.")
                             return None

                print(f"DEBUG: Using config for bank: {self.bank_config['name']}")

                # --- Find the definitive header location ---
                header_text = self.find_header(pdf[0]) # Check page 1
                header_page_index = 0
                if not header_text:
                     if len(pdf) > 1:
                         print("DEBUG: Header not found on page 1, trying page 2...")
                         header_text = self.find_header(pdf[1]) # Check page 2
                         if header_text:
                              header_page_index = 1
                              print(f"DEBUG: Header found on Page {header_page_index + 1}.")
                         else:
                             print("Error: Header pattern not found in the first few pages.")
                             return None # Fail if header isn't found early
                     else:
                          print("Error: Header pattern not found on the only page.")
                          return None # Fail if header not found on single page PDF
                else:
                     print(f"DEBUG: Header found on Page {header_page_index + 1}.")


                # --- Parse pages starting from where header was found ---
                result_df = pd.DataFrame()
                header_found_on_this_page = True # Flag for the first page being processed

                for i, page_text in enumerate(pdf):
                    if i < header_page_index:
                        continue # Skip pages before the header

                    print(f"Processing page {i+1}...")
                    # Pass the full page text and whether header should be sought
                    df_page = self.parse_page(page_text, expect_header=header_found_on_this_page)
                    header_found_on_this_page = False # Header only expected on the first page processed

                    if df_page is not None and not df_page.empty:
                        result_df = pd.concat([result_df, df_page], ignore_index=True)

                if result_df.empty:
                    print("Warning: No transactions were parsed from the PDF.")
                    # Consider if returning an empty DataFrame is better than None here
                    return None # Indicate failure if no transactions parsed

                # --- Rename columns and save ---
                if 'column_mapping' in self.bank_config:
                    try:
                        result_df.rename(columns=self.bank_config['column_mapping'], inplace=True)
                        print("DEBUG: Renamed columns based on mapping.")
                    except Exception as rename_err:
                        print(f"Warning: Error during column renaming: {rename_err}")


                if excel_file:
                    try:
                        result_df.to_excel(excel_file, index=False)
                        print(f"DEBUG: Successfully saved all parsed transactions to {excel_file}")
                    except Exception as e:
                        print(f"Error saving DataFrame to Excel: {e}")
                        # Decide if failure to save should return None or the DataFrame
                        return None # Return None if saving fails

                return result_df

        except pdftotext.Error as e:
             print(f"pdftotext error: {e}")
             return None
        except FileNotFoundError:
             print(f"Error: PDF file not found at {pdf_file}")
             return None
        except Exception as e:
            print(f"An unexpected error occurred during PDF parsing: {e}")
            traceback.print_exc() # Print full traceback for debugging
            return None


def parse_bank_statement(pdf_file, excel_output=None, bank_key=None):
    """
    Parse a bank statement PDF and optionally save to Excel.

    Args:
        pdf_file: Path to the bank statement PDF
        excel_output: Optional path to save Excel output
        bank_key: Optional key to specify the bank (SBI, HDFC, UNION, etc.)

    Returns:
        DataFrame with parsed transactions, or None on failure.
    """
    bank_config = BANKS.get(bank_key) if bank_key else None
    parser_instance = BankStatementParser(bank_config) # Renamed to avoid confusion with module
    result = parser_instance.parse_pdf(pdf_file, excel_output)
    # Return None explicitly if parsing failed or result is empty
    return result if result is not None and not result.empty else None


# Maintain backward compatibility
def parser(file, excel_file):
    """Legacy function for backward compatibility."""
    print("Warning: Using legacy 'parser' function. Please use 'parse_bank_statement' instead.")
    return parse_bank_statement(file, excel_file)

# --- END OF FILE parser.py ---