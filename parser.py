import pdftotext
import re
import pandas as pd
import openpyxl
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import tempfile
import os
import importlib.util
import sys

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
    'header': r"(?i)Date.*Narration.*Chq\/Ref\.No.*Value\s+Dt.*Withdrawal\s+Amt.*Deposit\s+Amt.*Closing\s+Balance",
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
            if bank_config['name'].lower() in page_text.lower():
                return bank_key
        
        # Try to detect based on header pattern
        for bank_key, bank_config in BANKS.items():
            if re.search(bank_config['header'], page_text):
                return bank_key
                
        return None
    
    def find_header(self, page_text):
        """Find the header row in the page text using the bank's header pattern."""
        if not self.bank_config:
            return None
            
        header = re.search(self.bank_config['header'], page_text)
        if header:
            return header.group(0)
        return None
    
    def extract_balance(self, balance_field):
        """Extract balance from the balance field."""
        if not self.bank_config or 'balance' not in self.bank_config:
            return balance_field
            
        m = re.match(self.bank_config['balance'], balance_field)
        if m:
            return m.group(1)
        return balance_field
    
    def parse_transaction_line(self, transaction_line):
        """Parse a transaction line based on the bank configuration."""
        if not self.bank_config:
            return None
            
        pattern = self.bank_config['transaction_pattern']
        mapping = self.bank_config['transaction_mapping']
        
        match = re.match(pattern, transaction_line, re.VERBOSE)
        if match:
            result = {}
            for field, group_index in mapping.items():
                result[field] = match.group(group_index)
            return result
        else:
            print(f"Warning: Could not parse transaction: {transaction_line}")
            return None
    
    def parse_all_transactions(self, header_index, lines):
        """Parse all transactions from the lines after the header."""
        if not self.bank_config:
            return []
            
        transactions_lines = lines[header_index+1:]
        transactions = []
        current_transaction = ""
        
        start_pattern = self.bank_config['transaction_start_pattern']
        
        for line in transactions_lines:
            if re.match(start_pattern, line.strip()):
                if current_transaction:
                    transactions.append(current_transaction)
                current_transaction = line
            else:
                current_transaction += " " + line.strip()
                
        # Don't forget the last transaction
        if current_transaction:
            transactions.append(current_transaction)
            
        return transactions
    
    def parse_transactions(self, transactions):
        """Parse a list of transaction lines into a DataFrame."""
        parsed_transactions = []
        for transaction in transactions:
            parsed = self.parse_transaction_line(transaction)
            if parsed:
                parsed_transactions.append(parsed)
                
        if parsed_transactions:
            return pd.DataFrame(parsed_transactions)
        return pd.DataFrame()
    
    def parse_page(self, page_text):
        """Parse a single page of the bank statement."""
        if not self.bank_config:
            return None
            
        header_index = -1
        lines = page_text.splitlines()
        
        for i, line in enumerate(lines):
            if re.search(self.bank_config['header'], line):
                header_index = i
                break
                
        if header_index == -1:
            print("Header not Found")
            return None
            
        transactions = self.parse_all_transactions(header_index, lines)
        df = self.parse_transactions(transactions)
        
        return df
    
    def parse_pdf(self, pdf_file, excel_file=None):
        """Parse a PDF bank statement and optionally save to Excel."""
        with open(pdf_file, "rb") as file:
            pdf = pdftotext.PDF(file, physical=True)
            first_page = pdf[0]
            
            # Auto-detect bank if not specified
            if not self.bank_config:
                bank_key = self.detect_bank(first_page)
                if bank_key and bank_key in BANKS:
                    self.bank_config = BANKS[bank_key]
                    print(f"Detected bank: {self.bank_config['name']}")
                else:
                    print("Unknown bank format. Please specify a supported bank.")
                    return None
            
            header_row = self.find_header(first_page)
            if not header_row:
                print("Header not found in the first page.")
                return None
                
            columns = re.split(r'\s{2,}', header_row.strip())
            result_df = pd.DataFrame()
            
            for page in pdf:
                df_page = self.parse_page(page)
                if df_page is not None and not df_page.empty:
                    # Rename columns according to bank's mapping
                    if 'column_mapping' in self.bank_config:
                        df_page.rename(columns=self.bank_config['column_mapping'], inplace=True)
                    result_df = pd.concat([result_df, df_page], ignore_index=True)
            
            # Process data if needed (e.g., filter debit transactions)
            if not result_df.empty and excel_file:
                # Check for 'Amount(Rs.)' or similar column to filter debits
                amount_col = next((col for col in result_df.columns if 'amount' in col.lower() or 'withdrawal' in col.lower()), None)
                if amount_col and 'dr' in self.bank_config.get('debit_indicator', '(Dr)').lower():
                    debit_df = result_df[result_df[amount_col].str.contains(self.bank_config.get('debit_indicator', '(Dr)'), regex=True)]
                    debit_df.to_excel(excel_file, index=False)
                else:
                    result_df.to_excel(excel_file, index=False)
            
            return result_df


def parse_bank_statement(pdf_file, excel_output=None, bank_key=None):
    """
    Parse a bank statement PDF and optionally save to Excel.
    
    Args:
        pdf_file: Path to the bank statement PDF
        excel_output: Optional path to save Excel output
        bank_key: Optional key to specify the bank (SBI, HDFC, etc.)
    
    Returns:
        DataFrame with parsed transactions
    """
    bank_config = BANKS.get(bank_key) if bank_key else None
    parser = BankStatementParser(bank_config)
    return parser.parse_pdf(pdf_file, excel_output)


# Maintain backward compatibility
def parser(file, excel_file):
    """Legacy function for backward compatibility."""
    return parse_bank_statement(file, excel_file)
