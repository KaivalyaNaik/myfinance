# --- START OF FILE parser.py ---

import pdftotext
import re
import pandas as pd
import numpy as np
import openpyxl # Required by pandas ExcelWriter, ensure installed
import os
import importlib.util
import sys
import traceback # Added for debugging unexpected errors

# --- Import Classifier ---
try:
    from classifier import add_classification
except ImportError:
    print("ERROR: classifier.py not found or add_classification function missing.")
    # Define a dummy function if import fails to avoid crashing later
    def add_classification(df):
        print("Warning: Classification module not loaded. Skipping classification.")
        if 'Category' not in df.columns:
             df['Category'] = 'Unavailable'
        return df
# --- End Import ---


# --- Constants Loading ---
# Explicitly modify sys.path to ensure the 'constants' module can be found
try:
    parser_script_dir = os.path.dirname(os.path.abspath(__file__))
    if parser_script_dir not in sys.path:
        sys.path.insert(0, parser_script_dir)
        print(f"DEBUG: Added '{parser_script_dir}' to sys.path for constants import.")
    from constants import banks
    BANKS = banks.BANKS
    print("DEBUG: Successfully imported constants using absolute import after sys.path modification.")
except ImportError as e:
     print(f"ERROR: Failed to import constants module even after modifying sys.path: {e}")
     print(f"Checked path added to sys.path: {parser_script_dir}")
     print("Please ensure 'banks.py' exists inside a 'constants' directory within the above path,")
     print("and that the 'constants' directory contains an '__init__.py' file.")
     sys.exit(1)
except Exception as e_gen:
     print(f"ERROR: An unexpected error occurred during constants loading: {e_gen}")
     traceback.print_exc()
     sys.exit(1)
# --- End Constants Loading ---


class BankStatementParser:
    """
    Parses bank statements from PDF files for configured banks.
    """
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.text = self._load_pdf()
        self.bank_config = None
        self.detected_bank = None

    def _load_pdf(self):
        """Loads text content from the PDF file."""
        try:
            with open(self.pdf_path, "rb") as f:
                # Using physical=True as it seemed necessary for header/structure
                pdf = pdftotext.PDF(f, physical=True)
            raw_text = "\n".join(pdf)
            cleaned_text = raw_text.replace('\uFB01', 'fi').replace('\uFB02', 'fl')
            cleaned_text = cleaned_text.replace('\x00', '')
            return cleaned_text
        except Exception as e:
            print(f"Error loading PDF {self.pdf_path}: {e}")
            traceback.print_exc()
            return ""

    def detect_bank(self):
        """Detects the bank based on keywords or patterns in the text."""
        # ... (detect_bank logic remains the same) ...
        if not self.text: print("PDF text is empty, cannot detect bank."); return None
        for bank_key, config in BANKS.items():
            if re.search(r'\b' + re.escape(config['name']) + r'\b', self.text, re.IGNORECASE):
                self.detected_bank = bank_key; self.bank_config = config
                print(f"Detected bank: {config['name']} ({bank_key})"); return bank_key
        print("Bank name not found directly, attempting header pattern matching...")
        lines = self.text.splitlines()
        for bank_key, config in BANKS.items():
             if 'header' in config:
                 header_pattern = re.compile(config['header'], re.IGNORECASE)
                 for i, line in enumerate(lines):
                     line_cleaned = re.sub(r'\s+', ' ', line).strip()
                     if header_pattern.search(line_cleaned):
                         start_pattern = config.get('transaction_start_pattern')
                         if start_pattern:
                             start_regex = re.compile(start_pattern)
                             found_start = False
                             for j in range(i + 1, min(i + 10, len(lines))):
                                 if start_regex.search(lines[j]): found_start = True; break
                             if found_start:
                                 self.detected_bank = bank_key; self.bank_config = config
                                 print(f"Detected bank via header/start pattern: {config['name']} ({bank_key})"); return bank_key
                         else:
                            self.detected_bank = bank_key; self.bank_config = config
                            print(f"Detected bank via header pattern: {config['name']} ({bank_key})"); return bank_key
        print("Could not detect a supported bank."); self.detected_bank = None; self.bank_config = None; return None


    def _clean_amount(self, amount_str):
        """Removes commas and converts amount string to float."""
        # ... (clean_amount logic remains the same) ...
        if isinstance(amount_str, (int, float)): return float(amount_str)
        if not isinstance(amount_str, str): return np.nan
        if not amount_str.strip(): return np.nan
        cleaned = re.sub(r"[^\d.]", "", amount_str.replace(',', ''))
        try: return float(cleaned) if cleaned and cleaned != '.' else np.nan
        except ValueError: return np.nan

    def _extract_transaction_amount_hdfc(self, block_text):
        """Extracts the single non-zero transaction amount from HDFC amount block."""
        if not isinstance(block_text, str):
            return np.nan
        # Find all potential amounts (like '1,234.56' or '150.00')
        amounts_found = re.findall(r"([\d,]+\.\d{2})", block_text)
        if not amounts_found:
            return np.nan # Or 0.0? NaN is safer for calculations

        # Clean and convert found amounts, return the first non-zero one
        for amount_str in amounts_found:
            num_amount = self._clean_amount(amount_str)
            if pd.notna(num_amount) and num_amount != 0:
                return num_amount
        return np.nan # Return NaN if only zero amounts or unparseable amounts were found

    def _determine_hdfc_amounts(self, df):
        """Determines Withdrawal/Deposit/Type for HDFC based on balance difference."""
        print("DEBUG: Determining HDFC amounts based on balance difference...")
        if df.empty:
            return df

        # Ensure required columns exist
        balance_col = self.bank_config['column_mapping']['balance']
        if balance_col not in df.columns or 'amount_block' not in df.columns:
             print(f"ERROR: Missing required columns ('{balance_col}', 'amount_block') for HDFC amount determination.")
             # Add empty columns if they don't exist
             if 'Withdrawal Amt.' not in df.columns: df['Withdrawal Amt.'] = 0.0
             if 'Deposit Amt.' not in df.columns: df['Deposit Amt.'] = 0.0
             if 'Type' not in df.columns: df['Type'] = None
             if 'Amount_Num' not in df.columns: df['Amount_Num'] = np.nan
             if 'Amount(Rs.)' not in df.columns: df['Amount(Rs.)'] = None
             return df

        # 1. Clean Balance and Calculate Difference
        df['balance_numeric'] = df[balance_col].apply(self._clean_amount)
        # Use shift(-1) to compare current balance with the *next* row's balance
        # Or use diff() which compares current to previous
        df['balance_diff'] = df['balance_numeric'].diff()

        # 2. Extract Transaction Amount from Amount Block
        df['transaction_amount'] = df['amount_block'].apply(self._extract_transaction_amount_hdfc)

        # 3. Determine Type, Withdrawal, Deposit
        df['Withdrawal Amt.'] = 0.0
        df['Deposit Amt.'] = 0.0
        df['Type'] = None

        # Handle first row separately (cannot use diff)
        # Fallback: Assume withdrawal if amount exists, otherwise 0. Needs improvement maybe.
        first_row_idx = df.index[0]
        first_row_amount = df.loc[first_row_idx, 'transaction_amount']
        if pd.notna(first_row_amount) and first_row_amount != 0:
             print(f"DEBUG: First HDFC row (idx {first_row_idx}), assuming Withdrawal for amount {first_row_amount}")
             df.loc[first_row_idx, 'Withdrawal Amt.'] = first_row_amount
             df.loc[first_row_idx, 'Type'] = 'Dr'
        # else: # Amount is NaN or 0
             # Leave as 0 withdrawal/deposit, Type None

        # Process remaining rows using balance difference
        # Use numpy.isclose for float comparison with tolerance
        tolerance = 0.01 # Tolerance of 1 paisa
        for i in range(1, len(df)):
            idx = df.index[i]
            diff = df.loc[idx, 'balance_diff']
            amount = df.loc[idx, 'transaction_amount']

            if pd.isna(diff) or pd.isna(amount):
                # Cannot determine type if diff or amount is missing
                print(f"DEBUG: Skipping row {idx} due to NaN diff ({diff}) or amount ({amount})")
                continue

            if np.isclose(diff, -amount, atol=tolerance):
                df.loc[idx, 'Withdrawal Amt.'] = amount
                df.loc[idx, 'Type'] = 'Dr'
            elif np.isclose(diff, amount, atol=tolerance):
                df.loc[idx, 'Deposit Amt.'] = amount
                df.loc[idx, 'Type'] = 'Cr'
            else:
                # Difference doesn't match amount (e.g., fees, interest, complex)
                # Fallback: Assign amount to withdrawal for now, mark type unknown
                print(f"Warning: Balance diff ({diff:.2f}) doesn't match amount ({amount:.2f}) for row {idx}. Assigning to Withdrawal, Type Unknown.")
                df.loc[idx, 'Withdrawal Amt.'] = amount # Or should it be deposit? Hard to tell.
                df.loc[idx, 'Type'] = 'Unknown'

        # 4. Create derived Amount_Num and Amount(Rs.)
        df['Amount_Num'] = df.apply(lambda row: row['Withdrawal Amt.'] if row['Type'] == 'Dr' else (row['Deposit Amt.'] if row['Type'] == 'Cr' else row.get('transaction_amount', np.nan)), axis=1)
        df['Amount(Rs.)'] = df.apply(lambda row: f"{row['Amount_Num']:.2f} ({row['Type']})" if pd.notna(row['Amount_Num']) and pd.notna(row['Type']) and row['Type'] != 'Unknown' else (f"{row['Amount_Num']:.2f} (?)" if pd.notna(row['Amount_Num']) else None), axis=1)

        # 5. Clean up intermediate columns
        df.drop(columns=['amount_block', 'balance_numeric', 'balance_diff', 'transaction_amount'], inplace=True, errors='ignore')

        print("DEBUG: Finished determining HDFC amounts.")
        return df


    def _parse_transactions(self):
        """
        Parses transaction data based on the detected bank's configuration.
        Handles multi-line entries and HDFC balance difference logic.
        """
        if not self.bank_config: print("Bank configuration not set."); return pd.DataFrame()

        lines = self.text.splitlines()
        transactions = []
        in_transaction_section = False
        header_found = False
        skipped_lines_count = 0

        header_pattern = re.compile(self.bank_config['header'], re.IGNORECASE)
        start_pattern_re = re.compile(self.bank_config.get('transaction_start_pattern', 'a^'))

        # Compile bank-specific regexes
        if self.detected_bank == 'HDFC':
            transaction_re = re.compile(self.bank_config['transaction_pattern'])
            narration_cont_re = re.compile(self.bank_config.get('narration_continuation_pattern', 'a^'))
        elif self.detected_bank == 'UNION_BANK':
            txn_re_same_line = re.compile(self.bank_config['transaction_pattern_same_line'])
            txn_re_multi_line = re.compile(self.bank_config['transaction_pattern_multi_line'])
            multi_line_balance_re = re.compile(self.bank_config.get('multi_line_balance_pattern', 'a^'))
            remarks_cont_re = re.compile(self.bank_config.get('remarks_continuation_pattern', 'a^'))
        else: # Fallback for other banks
            transaction_re = re.compile(self.bank_config.get('transaction_pattern', 'a^'))

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            line_cleaned_header_match = re.sub(r'\s+', ' ', line).strip()

            # --- Header Detection ---
            if not header_found and header_pattern.search(line_cleaned_header_match):
                in_transaction_section = True; header_found = True
                print(f"DEBUG: Found header on line {i}: '{line_cleaned_header_match}'"); i += 1; continue
            if not in_transaction_section: i += 1; continue

            # --- Stop Conditions ---
            # ... (Stop condition logic remains the same) ...
            if not line and transactions and i > 0 and not lines[i-1].strip():
                 if all(not l.strip() for l in lines[i+1:min(i+4, len(lines))]): print(f"Stopping parse on encountering multiple blank lines (line {i})."); break
            stop_patterns = [r"Statement Summary", r"TOTAL DEBITS",r"This is system generated",r"Request to out customers", r"Transactions legend:",r"Minimum Balance", r"Average Monthly", r"Interest rate",r"If you have any queries", r"Please quote your",r"^\s*Generated On:",r"STATEMENT SUMMARY :-",r"^\s*Closing Balance\s+[\d,\.]+\s+Cr\s*$"]
            should_stop = False
            if transactions:
                for pattern in stop_patterns:
                    if re.search(pattern, line, re.IGNORECASE): should_stop = True; print(f"Stopping parse on encountering footer/summary line {i}: '{line}'"); break
            if should_stop: break

            # --- Transaction Matching ---
            match_found = False; data = None; mapping = None; consumed_lines = 0

            # --- HDFC Logic (Uses new pattern) ---
            if self.detected_bank == 'HDFC':
                match = transaction_re.match(line) # Match against original stripped line
                if match:
                    skipped_lines_count = 0; match_found = True
                    data = list(match.groups())
                    mapping = self.bank_config['transaction_mapping'] # Includes 'amount_block' now
                    # Narration continuation logic
                    narration_part1 = data[mapping['narration'] - 1]
                    narration_parts = [narration_part1.strip()] if narration_part1 else []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line or start_pattern_re.search(lines[j].strip()) or not narration_cont_re.match(next_line): break
                        narration_parts.append(next_line); consumed_lines += 1; j += 1
                    full_narration = " ".join(narration_parts)
                    data[mapping['narration'] - 1] = full_narration
                else:
                    if line and start_pattern_re.search(line): skipped_lines_count += 1

            # --- Union Bank Logic (Remains the same) ---
            elif self.detected_bank == 'UNION_BANK':
                # ... (Union bank logic remains the same as previous version) ...
                match_same = txn_re_same_line.match(line)
                if match_same:
                    skipped_lines_count = 0; match_found = True; data = list(match_same.groups()); mapping = self.bank_config['transaction_mapping_same_line']
                    remarks_part1 = data[mapping['remarks'] - 1]; remarks_parts = [remarks_part1.strip()] if remarks_part1 else []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        if not next_line or start_pattern_re.search(lines[j].strip()) or multi_line_balance_re.match(next_line) or not remarks_cont_re.match(next_line): break
                        remarks_parts.append(next_line); consumed_lines += 1; j += 1
                    full_remarks = " ".join(part for part in remarks_parts if part); data[mapping['remarks'] - 1] = full_remarks
                else:
                    match_multi = txn_re_multi_line.match(line)
                    if match_multi:
                        skipped_lines_count = 0; match_found = True; data = list(match_multi.groups()); mapping = self.bank_config['transaction_mapping_multi_line']
                        balance_value = None; remarks_part1 = data[mapping['remarks'] - 1]; remarks_parts = [remarks_part1.strip()] if remarks_part1 else []
                        j = i + 1; balance_found_on_next = False
                        while j < len(lines):
                            next_line = lines[j].strip()
                            if not balance_found_on_next:
                                balance_match = multi_line_balance_re.match(next_line)
                                if balance_match: balance_value = balance_match.group(1); balance_found_on_next = True; consumed_lines += 1; j += 1; continue
                            if remarks_cont_re.match(next_line): remarks_parts.append(next_line); consumed_lines += 1; j += 1
                            else: break
                        full_remarks = " ".join(part for part in remarks_parts if part); data[mapping['remarks'] - 1] = full_remarks
                        balance_idx = list(mapping.keys()).index('balance');
                        while len(data) <= balance_idx: data.append(None)
                        data[balance_idx] = balance_value
                    else:
                        if line and start_pattern_re.search(line): skipped_lines_count += 1


            # --- Process Matched Data ---
            if match_found and data and mapping:
                current_transaction = {}
                # Populate transaction dict based on mapping
                for col, map_index in mapping.items():
                    target_col_name = self.bank_config['column_mapping'].get(col, col)
                    value = None
                    # Handle direct mapping from regex group
                    if map_index is not None:
                        if (map_index - 1) < len(data) and data[map_index - 1] is not None:
                             value = data[map_index - 1]
                    # Handle special cases (like Union Bank multi-line balance)
                    elif col == 'balance' and self.detected_bank == 'UNION_BANK':
                        balance_idx_in_map = list(mapping.keys()).index('balance')
                        if balance_idx_in_map < len(data) and data[balance_idx_in_map] is not None:
                             value = data[balance_idx_in_map]
                    # Handle HDFC derived columns (will be populated later)
                    elif self.detected_bank == 'HDFC' and col in ['withdrawal', 'deposit']:
                         value = None # Placeholder, will be derived
                    else:
                         # Assign None if map_index is None and not handled above
                         value = None

                    current_transaction[target_col_name] = value.strip() if isinstance(value, str) else value

                transactions.append(current_transaction)
                i += (1 + consumed_lines)
                continue

            # --- If no match, advance to next line ---
            i += 1

        # --- Post-Processing and DataFrame Creation ---
        if not transactions:
            if not header_found: print("Parsing Error: Header pattern never matched.")
            else: print("No transactions found matching the pattern after the header.")
            return pd.DataFrame()

        df = pd.DataFrame(transactions)

        # --- Data Cleaning / Type Conversion / Derivations ---
        if self.detected_bank == 'HDFC':
            # Apply the balance difference logic to derive amounts/type
            df = self._determine_hdfc_amounts(df)
            date_col = self.bank_config['column_mapping']['date']
            final_balance_col_name = f"{self.bank_config['column_mapping']['balance']}_Num" # Construct expected name
        elif self.detected_bank == 'UNION_BANK' or self.detected_bank == 'SBI':
            # Apply standard amount/type extraction for Union/SBI
            amount_col = self.bank_config['column_mapping']['amount']
            balance_col_orig = self.bank_config['column_mapping']['balance']
            date_col = self.bank_config['column_mapping']['date']
            def extract_amount_type(amount_str):
                if not isinstance(amount_str, str): return None, None
                val = self._clean_amount(amount_str); type_ = 'Dr' if '(Dr)' in amount_str else ('Cr' if '(Cr)' in amount_str else None); return val, type_
            if amount_col in df.columns: df[['Amount_Num', 'Type']] = df[amount_col].apply(lambda x: pd.Series(extract_amount_type(x)))
            else: print(f"Warning: Expected amount column '{amount_col}' not found."); df['Amount_Num'] = np.nan; df['Type'] = None
            if balance_col_orig in df.columns:
                cleaned_balance_col_orig = re.sub(r'[ /.\(\)]+', '_', str(balance_col_orig)).strip('_'); final_balance_col_name = f'{cleaned_balance_col_orig}_Num'; df[final_balance_col_name] = df[balance_col_orig].apply(self._clean_amount)
            else: print(f"Warning: Expected balance column '{balance_col_orig}' not found.")

        # Convert Date column
        if date_col and date_col in df.columns:
             date_format = '%d/%m/%y' if self.detected_bank == 'HDFC' else '%d/%m/%Y'
             try: df[date_col] = pd.to_datetime(df[date_col], errors='coerce', format=date_format)
             except Exception as e: print(f"Warning: Could not parse date column '{date_col}' with format {date_format}. Error: {e}"); df[date_col] = pd.NaT

        # Reorder columns
        # ... (Column reordering logic - adjust based on derived HDFC cols) ...
        desired_cols = []
        if date_col in df.columns: desired_cols.append(date_col)
        # Define core keys based on what should be present after processing
        core_keys = ['transaction_id', 'remarks', 'narration', 'ref_no', 'value_dt',
                     'withdrawal', 'deposit', 'amount', 'balance'] # Original names from mapping
        for key in core_keys:
            col_name = self.bank_config['column_mapping'].get(key)
            if col_name and col_name in df.columns and col_name not in desired_cols:
                desired_cols.append(col_name)
        # Add derived columns (standard names)
        if 'Amount(Rs.)' in df.columns and 'Amount(Rs.)' not in desired_cols: desired_cols.append('Amount(Rs.)')
        if final_balance_col_name and final_balance_col_name in df.columns: desired_cols.append(final_balance_col_name)
        if 'Amount_Num' in df.columns: desired_cols.append('Amount_Num')
        if 'Type' in df.columns: desired_cols.append('Type')
        remaining_cols = [col for col in df.columns if col not in desired_cols]
        final_cols = desired_cols + remaining_cols
        final_cols = [col for col in final_cols if col in df.columns] # Ensure all exist

        return df[final_cols]


    def parse(self):
        """Detects the bank and parses the transactions."""
        # ... (parse logic remains the same) ...
        if not self.text: print("PDF content is empty. Cannot parse."); return pd.DataFrame()
        if self.detect_bank():
            try:
                df = self._parse_transactions(); print(f"Successfully parsed {len(df)} transactions.")
                if df.empty and header_found: print("Warning: Header was found, but no transactions were successfully parsed.")
                elif df.empty and not header_found: print("Warning: Header not found, and no transactions parsed.")
                return df
            except Exception as e: print(f"An error occurred during parsing for {self.detected_bank}: {e}"); traceback.print_exc(); return pd.DataFrame()
        else: print("Bank detection failed. Cannot parse transactions."); return pd.DataFrame()


def parse_bank_statement(pdf_path):
    """Convenience function to parse a bank statement PDF. Adds classification."""
    # ... (remains the same, calls add_classification and cleans columns) ...
    if not os.path.exists(pdf_path): print(f"Error: PDF file not found at {pdf_path}"); return pd.DataFrame()
    parser = BankStatementParser(pdf_path); parsed_df = parser.parse()
    if parsed_df is not None and not parsed_df.empty:
        print("Applying classification rules..."); parsed_df = add_classification(parsed_df); print("Classification complete.")
        print("Cleaning column names for final output..."); cleaned_columns = {}
        cols_to_clean = list(parsed_df.columns)
        if 'Category' in parsed_df.columns and 'Category' not in cols_to_clean: cols_to_clean.append('Category')
        for col in cols_to_clean:
            if col not in parsed_df.columns: continue
            new_col = str(col); new_col = re.sub(r'[ /.\(\)]+', '_', new_col); new_col = re.sub(r'_+', '_', new_col); new_col = new_col.strip('_')
            count = 1; original_new_col = new_col
            while new_col in cleaned_columns.values(): new_col = f"{original_new_col}_{count}"; count += 1
            cleaned_columns[col] = new_col
        parsed_df.rename(columns=cleaned_columns, inplace=True); print("Column names cleaned.")
    return parsed_df


# # Example usage block - COMMENTED OUT
# if __name__ == '__main__':
#     pass

# --- END OF FILE parser.py ---
