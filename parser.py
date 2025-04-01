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

# --- Constants Loading ---
# Dynamically load bank configurations from constants/banks.py
constants_path = os.path.join(os.path.dirname(__file__), 'constants', 'banks.py')
spec = importlib.util.spec_from_file_location("banks_config", constants_path)
banks_config_module = importlib.util.module_from_spec(spec)
sys.modules["banks_config"] = banks_config_module
spec.loader.exec_module(banks_config_module)
BANKS = banks_config_module.BANKS
# --- End Constants Loading ---


class BankStatementParser:
    """
    Parses bank statements from PDF files for configured banks.
    """
    def __init__(self, pdf_path):
        """
        Initializes the parser with the path to the PDF file.

        Args:
            pdf_path (str): The file path to the PDF bank statement.
        """
        self.pdf_path = pdf_path
        self.text = self._load_pdf()
        self.bank_config = None
        self.detected_bank = None

    def _load_pdf(self):
        """Loads text content from the PDF file."""
        try:
            with open(self.pdf_path, "rb") as f:
                # Using layout preservation often helps with table structure
                pdf = pdftotext.PDF(f, physical=True)
            # Simple text cleaning: replace common ligature issues
            raw_text = "\n".join(pdf)
            cleaned_text = raw_text.replace('\uFB01', 'fi').replace('\uFB02', 'fl') # common ligatures
            return cleaned_text
        except Exception as e:
            print(f"Error loading PDF {self.pdf_path}: {e}")
            traceback.print_exc() # Print detailed traceback
            return ""

    def detect_bank(self):
        """
        Detects the bank based on keywords or patterns in the text.
        Sets self.bank_config and self.detected_bank.
        """
        if not self.text:
            print("PDF text is empty, cannot detect bank.")
            return None

        # Simple detection based on bank name first
        for bank_key, config in BANKS.items():
            if re.search(r'\b' + re.escape(config['name']) + r'\b', self.text, re.IGNORECASE):
                self.detected_bank = bank_key
                self.bank_config = config
                print(f"Detected bank: {config['name']} ({bank_key})")
                return bank_key

        # Fallback: Try detecting based on header patterns if name not found
        print("Bank name not found directly, attempting header pattern matching...")
        lines = self.text.splitlines()
        for bank_key, config in BANKS.items():
             if 'header' in config:
                 header_pattern = re.compile(config['header'], re.IGNORECASE)
                 for i, line in enumerate(lines):
                     line_cleaned = re.sub(r'\s+', ' ', line).strip() # Clean for header match
                     if header_pattern.search(line_cleaned):
                         start_pattern = config.get('transaction_start_pattern')
                         if start_pattern:
                             start_regex = re.compile(start_pattern)
                             found_start = False
                             for j in range(i + 1, min(i + 10, len(lines))):
                                 # Match start pattern against original line structure
                                 if start_regex.search(lines[j]):
                                     found_start = True
                                     break
                             if found_start:
                                 self.detected_bank = bank_key
                                 self.bank_config = config
                                 print(f"Detected bank via header/start pattern: {config['name']} ({bank_key})")
                                 return bank_key
                         else:
                            self.detected_bank = bank_key
                            self.bank_config = config
                            print(f"Detected bank via header pattern: {config['name']} ({bank_key})")
                            return bank_key

        print("Could not detect a supported bank.")
        self.detected_bank = None
        self.bank_config = None
        return None


    def _clean_amount(self, amount_str):
        """Removes commas and converts amount string to float."""
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        if not isinstance(amount_str, str):
            return np.nan
        cleaned = re.sub(r"[^\d.]", "", amount_str.replace(',', ''))
        try:
            return float(cleaned) if cleaned and cleaned != '.' else np.nan
        except ValueError:
            return np.nan


    def _parse_transactions(self):
        """
        Parses transaction data based on the detected bank's configuration.
        Handles multi-line entries specifically for HDFC and Union Bank.
        """
        if not self.bank_config:
            print("Bank configuration not set. Cannot parse transactions.")
            return pd.DataFrame()

        lines = self.text.splitlines()
        transactions = []
        in_transaction_section = False
        header_found = False # Track if header was ever found
        skipped_lines_count = 0 # Count lines skipped after header

        # Compile necessary regex patterns from config
        header_pattern = re.compile(self.bank_config['header'], re.IGNORECASE)
        start_pattern_re = re.compile(self.bank_config.get('transaction_start_pattern', 'a^')) # Dummy if not present

        # --- Bank-Specific Regex Compilation ---
        if self.detected_bank == 'HDFC':
            transaction_re = re.compile(self.bank_config['transaction_pattern'])
            narration_cont_re = re.compile(self.bank_config.get('narration_continuation_pattern', 'a^'))
        elif self.detected_bank == 'UNION_BANK':
            txn_re_same_line = re.compile(self.bank_config['transaction_pattern_same_line'])
            txn_re_multi_line = re.compile(self.bank_config['transaction_pattern_multi_line'])
            multi_line_balance_re = re.compile(self.bank_config.get('multi_line_balance_pattern', 'a^'))
            remarks_cont_re = re.compile(self.bank_config.get('remarks_continuation_pattern', 'a^'))
        else:
            transaction_re = re.compile(self.bank_config.get('transaction_pattern', 'a^'))


        i = 0
        while i < len(lines):
            line = lines[i].strip()
            line_cleaned = re.sub(r'\s+', ' ', line).strip() # Cleaned version for header matching

            # --- Header Detection ---
            if not header_found and header_pattern.search(line_cleaned):
                in_transaction_section = True
                header_found = True
                print(f"DEBUG: Found header on line {i}: '{line_cleaned}'")
                i += 1
                continue

            if not in_transaction_section:
                i += 1
                continue

            # --- Stop Conditions ---
            if not line and transactions and i > 0 and not lines[i-1].strip():
                 if all(not l.strip() for l in lines[i+1:min(i+4, len(lines))]):
                     print(f"Stopping parse on encountering multiple blank lines (line {i}).")
                     break

            # REMOVED "Registered office:", REMOVED specific Closing Balance line pattern
            stop_patterns = [
                 r"Statement Summary", r"TOTAL DEBITS", # Keep TOTAL CREDITS?
                 # r"NEFT:", r"RTGS:", r"UPI:", r"INT:", r"HBPS:", # These might appear in remarks
                 r"This is system generated",
                 r"Request to out customers", r"Transactions legend:",
                 r"Minimum Balance", r"Average Monthly", r"Interest rate",
                 r"If you have any queries", r"Please quote your",
                 r"^\s*Generated On:",
                 # Add pattern for HDFC end summary table start
                 r"STATEMENT SUMMARY :-",
                 # Add pattern for Union Bank end summary table start (if identifiable)
                 # Example: r"^\s*Closing Balance\s*$", # A line just saying "Closing Balance"
                 # Union bank specific end marker?
                 r"^\s*Closing Balance\s+[\d,\.]+\s+Cr\s*$" # Match the final closing balance line
            ]
            should_stop = False
            if transactions: # Only check stop patterns if we've started parsing
                for pattern in stop_patterns:
                    # Use original line for stop pattern matching as regex might be specific
                    if re.search(pattern, line, re.IGNORECASE):
                        should_stop = True
                        print(f"Stopping parse on encountering footer/summary line {i}: '{line}'")
                        break
            if should_stop:
                 break

            # --- Transaction Matching ---
            match_found = False
            data = None
            mapping = None
            consumed_lines = 0

            # --- HDFC Specific Logic ---
            if self.detected_bank == 'HDFC':
                # Use the ORIGINAL line for matching HDFC transactions now
                match = transaction_re.match(line)
                if match:
                    skipped_lines_count = 0 # Reset skipped lines counter on match
                    match_found = True
                    data = list(match.groups())
                    mapping = self.bank_config['transaction_mapping']
                    narration_part1 = data[mapping['narration'] - 1]
                    narration_parts = [narration_part1.strip()] if narration_part1 else []

                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        # Use original next_line for start pattern check
                        if not next_line or start_pattern_re.search(lines[j]) or not narration_cont_re.match(next_line):
                            break
                        narration_parts.append(next_line)
                        consumed_lines += 1
                        j += 1
                    full_narration = " ".join(narration_parts)
                    data[mapping['narration'] - 1] = full_narration
                else:
                    # DEBUG: Print lines that don't match in HDFC section
                    if line and start_pattern_re.search(line): # Only print if it looks like a txn start
                        # print(f"DEBUG HDFC: No transaction match on line {i}: '{line}'") # Keep commented unless debugging HDFC
                        skipped_lines_count += 1


            # --- Union Bank Specific Logic ---
            elif self.detected_bank == 'UNION_BANK':
                # Use the original line for matching Union Bank
                match_same = txn_re_same_line.match(line)
                if match_same:
                    skipped_lines_count = 0
                    match_found = True
                    data = list(match_same.groups())
                    mapping = self.bank_config['transaction_mapping_same_line']
                    remarks_part1 = data[mapping['remarks'] - 1]
                    remarks_parts = [remarks_part1.strip()] if remarks_part1 else []
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j].strip()
                        # Use original next_line for start pattern check
                        if not next_line or start_pattern_re.search(lines[j]) or multi_line_balance_re.match(next_line) or not remarks_cont_re.match(next_line):
                            break
                        remarks_parts.append(next_line)
                        consumed_lines += 1
                        j += 1
                    full_remarks = " ".join(part for part in remarks_parts if part)
                    data[mapping['remarks'] - 1] = full_remarks

                else:
                    match_multi = txn_re_multi_line.match(line)
                    if match_multi:
                        skipped_lines_count = 0
                        match_found = True
                        data = list(match_multi.groups())
                        mapping = self.bank_config['transaction_mapping_multi_line']
                        balance_value = None
                        remarks_part1 = data[mapping['remarks'] - 1]
                        remarks_parts = [remarks_part1.strip()] if remarks_part1 else []

                        j = i + 1
                        balance_found_on_next = False
                        while j < len(lines):
                            next_line = lines[j].strip()
                            if not balance_found_on_next:
                                balance_match = multi_line_balance_re.match(next_line)
                                if balance_match:
                                    balance_value = balance_match.group(1)
                                    balance_found_on_next = True
                                    consumed_lines += 1
                                    j += 1
                                    continue
                            if remarks_cont_re.match(next_line):
                                remarks_parts.append(next_line)
                                consumed_lines += 1
                                j += 1
                            else: break

                        full_remarks = " ".join(part for part in remarks_parts if part)
                        data[mapping['remarks'] - 1] = full_remarks
                        balance_idx = list(mapping.keys()).index('balance')
                        while len(data) <= balance_idx: data.append(None)
                        data[balance_idx] = balance_value
                    else:
                        # *** DEBUG LINE IS ACTIVE FOR UNION BANK ***
                        # Print lines that don't match either pattern in Union Bank section
                        if line and start_pattern_re.search(line): # Only print if it looks like a txn start
                            print(f"DEBUG UNION: No transaction match on line {i}: '{line}'")
                            skipped_lines_count += 1


            # --- Generic Bank Logic ---
            else:
                 if transaction_re.pattern != 'a^':
                     match = transaction_re.match(line) # Use original line
                     if match:
                         skipped_lines_count = 0
                         match_found = True
                         data = list(match.groups())
                         mapping = self.bank_config['transaction_mapping']


            # --- Process Matched Data ---
            if match_found and data and mapping:
                current_transaction = {}
                for col, map_index in mapping.items():
                    target_col_name = self.bank_config['column_mapping'].get(col, col)
                    value = None
                    if map_index is not None: # Standard mapping
                        if (map_index - 1) < len(data) and data[map_index - 1] is not None:
                             value = data[map_index - 1]
                    elif col == 'balance' and self.detected_bank == 'UNION_BANK': # Special multi-line
                        balance_idx_in_map = list(mapping.keys()).index('balance')
                        if balance_idx_in_map < len(data) and data[balance_idx_in_map] is not None:
                             value = data[balance_idx_in_map]

                    current_transaction[target_col_name] = value.strip() if isinstance(value, str) else value

                transactions.append(current_transaction)
                i += (1 + consumed_lines)
                continue

            # --- If no match, advance to next line ---
            i += 1


        # --- Post-Processing and DataFrame Creation ---
        if not transactions:
            if not header_found:
                 print("Parsing Error: Header pattern never matched.")
            else:
                 print("No transactions found matching the pattern after the header.")
            return pd.DataFrame()

        df = pd.DataFrame(transactions)

        # --- Data Cleaning and Type Conversion ---
        balance_col = None
        date_col = None
        final_balance_col_name = None # Store the final numeric balance column name

        if self.detected_bank == 'HDFC':
            balance_col_orig = self.bank_config['column_mapping']['balance']
            date_col = self.bank_config['column_mapping']['date']
            withdrawal_col = self.bank_config['column_mapping']['withdrawal']
            deposit_col = self.bank_config['column_mapping']['deposit']

            if withdrawal_col in df.columns: df[withdrawal_col] = df[withdrawal_col].apply(self._clean_amount)
            if deposit_col in df.columns: df[deposit_col] = df[deposit_col].apply(self._clean_amount)
            if balance_col_orig in df.columns:
                final_balance_col_name = f'{balance_col_orig}_Num'
                df[final_balance_col_name] = df[balance_col_orig].apply(self._clean_amount)

            df['Amount_Num'] = df.apply(lambda row: row.get(withdrawal_col) if pd.notna(row.get(withdrawal_col)) and row.get(withdrawal_col) != 0 else row.get(deposit_col), axis=1)
            df['Type'] = df.apply(lambda row: 'Dr' if pd.notna(row.get(withdrawal_col)) and row.get(withdrawal_col) != 0 else ('Cr' if pd.notna(row.get(deposit_col)) and row.get(deposit_col) != 0 else None), axis=1)
            df['Amount(Rs.)'] = df.apply(lambda row: f"{row['Amount_Num']:.2f} ({row['Type']})" if pd.notna(row['Amount_Num']) and pd.notna(row['Type']) else None, axis=1)


        elif self.detected_bank == 'UNION_BANK' or self.detected_bank == 'SBI':
            amount_col = self.bank_config['column_mapping']['amount']
            balance_col_orig = self.bank_config['column_mapping']['balance']
            date_col = self.bank_config['column_mapping']['date']

            def extract_amount_type(amount_str):
                if not isinstance(amount_str, str): return None, None
                val = self._clean_amount(amount_str)
                type_ = 'Dr' if '(Dr)' in amount_str else ('Cr' if '(Cr)' in amount_str else None)
                return val, type_

            if amount_col in df.columns:
                df[['Amount_Num', 'Type']] = df[amount_col].apply(lambda x: pd.Series(extract_amount_type(x)))
            if balance_col_orig in df.columns:
                final_balance_col_name = f'{balance_col_orig}_Num'
                df[final_balance_col_name] = df[balance_col_orig].apply(self._clean_amount)


        # Convert Date column
        if date_col and date_col in df.columns:
             date_format = '%d/%m/%y' if self.detected_bank == 'HDFC' else '%d/%m/%Y'
             try:
                 df[date_col] = pd.to_datetime(df[date_col], errors='coerce', format=date_format)
             except Exception as e:
                 print(f"Warning: Could not parse date column '{date_col}' with format {date_format}. Error: {e}")
                 df[date_col] = pd.NaT

        # Reorder columns
        desired_cols = []
        if date_col in df.columns: desired_cols.append(date_col)
        core_keys = ['transaction_id', 'remarks', 'narration', 'ref_no', 'value_dt',
                     'withdrawal', 'deposit', 'amount', 'balance']
        for key in core_keys:
            col_name = self.bank_config['column_mapping'].get(key)
            if col_name and col_name in df.columns and col_name not in desired_cols:
                desired_cols.append(col_name)

        if 'Amount(Rs.)' in df.columns and 'Amount(Rs.)' not in desired_cols: desired_cols.append('Amount(Rs.)')
        if final_balance_col_name and final_balance_col_name in df.columns: desired_cols.append(final_balance_col_name)
        if 'Amount_Num' in df.columns: desired_cols.append('Amount_Num')
        if 'Type' in df.columns: desired_cols.append('Type')

        remaining_cols = [col for col in df.columns if col not in desired_cols]
        final_cols = desired_cols + remaining_cols
        final_cols = [col for col in final_cols if col in df.columns]

        return df[final_cols]


    def parse(self):
        """
        Detects the bank and parses the transactions.

        Returns:
            pandas.DataFrame: A DataFrame containing the parsed transactions,
                              or an empty DataFrame if detection or parsing fails.
        """
        if not self.text:
             print("PDF content is empty. Cannot parse.")
             return pd.DataFrame()

        if self.detect_bank():
            try:
                df = self._parse_transactions()
                print(f"Successfully parsed {len(df)} transactions.")
                # Add check for empty dataframe after parsing attempt
                if df.empty and header_found:
                     print("Warning: Header was found, but no transactions were successfully parsed.")
                elif df.empty and not header_found:
                     print("Warning: Header not found, and no transactions parsed.")

                return df
            except Exception as e:
                print(f"An error occurred during parsing for {self.detected_bank}: {e}")
                traceback.print_exc()
                return pd.DataFrame()
        else:
            print("Bank detection failed. Cannot parse transactions.")
            return pd.DataFrame()


def parse_bank_statement(pdf_path):
    """
    Convenience function to parse a bank statement PDF.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        pandas.DataFrame: Parsed transaction data, or empty DataFrame if parsing fails.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return pd.DataFrame() # Return empty DF

    parser = BankStatementParser(pdf_path)
    parsed_df = parser.parse()

    if parsed_df is None: # Should not happen based on parse() logic, but check anyway
        print(f"Parsing returned None unexpectedly for {pdf_path}")
        return pd.DataFrame()
    elif not parsed_df.empty:
        # Clean column names only if DataFrame is not empty
        cleaned_columns = {}
        for col in parsed_df.columns:
            new_col = str(col)
            new_col = re.sub(r'[ /.\(\)]+', '_', new_col)
            new_col = re.sub(r'_+', '_', new_col)
            new_col = new_col.strip('_')
            count = 1
            original_new_col = new_col
            while new_col in cleaned_columns.values():
                new_col = f"{original_new_col}_{count}"
                count += 1
            cleaned_columns[col] = new_col
        parsed_df.rename(columns=cleaned_columns, inplace=True)

    return parsed_df # Return DataFrame (potentially empty)


# Example usage (for testing purposes)
if __name__ == '__main__':
    # --- Test with Union Bank PDF ---
    test_pdf_path_union = 'union_unlocked.pdf'
    if os.path.exists(test_pdf_path_union):
        print(f"\n--- Testing Parser with {test_pdf_path_union} ---")
        df_result_union = parse_bank_statement(test_pdf_path_union)
        if df_result_union is not None and not df_result_union.empty:
            print("\n--- Union Bank Parsing Successful ---")
            print(f"Number of transactions parsed: {len(df_result_union)}")
            # print("\nFirst 5 rows:") # Keep output concise for debugging
            # print(df_result_union.head())
            # print("\nLast 5 rows:")
            # print(df_result_union.tail())
            output_filename_union = "parsed_union_bank_test_output.xlsx"
            try:
                df_result_union.to_excel(output_filename_union, index=False)
                print(f"\nSaved parsed data to {output_filename_union}")
            except Exception as e:
                 print(f"\nError saving Union Bank results to Excel: {e}")
        else:
            print("\n--- Union Bank Parsing Failed or No Data ---")
    else:
        print(f"\nTest PDF not found at '{test_pdf_path_union}'. Skipping Union Bank test run.")

    # --- Test with HDFC PDF ---
    test_pdf_path_hdfc = 'march.pdf'
    if os.path.exists(test_pdf_path_hdfc):
        print(f"\n--- Testing Parser with {test_pdf_path_hdfc} ---")
        df_result_hdfc = parse_bank_statement(test_pdf_path_hdfc)
        if df_result_hdfc is not None and not df_result_hdfc.empty:
             print("\n--- HDFC Parsing Successful ---")
             print(f"Number of transactions parsed: {len(df_result_hdfc)}")
             # print("\nFirst 5 rows:") # Keep output concise for debugging
             # print(df_result_hdfc.head())
             output_filename_hdfc = "parsed_hdfc_test_output.xlsx"
             try:
                 df_result_hdfc.to_excel(output_filename_hdfc, index=False)
                 print(f"\nSaved parsed data to {output_filename_hdfc}")
             except Exception as e:
                 print(f"\nError saving HDFC results to Excel: {e}")
        else:
             print("\n--- HDFC Parsing Failed or No Data ---")
    else:
        print(f"\nTest PDF not found at '{test_pdf_path_hdfc}'. Skipping HDFC test run.")

# --- END OF FILE parser.py ---
