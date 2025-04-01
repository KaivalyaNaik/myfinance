# Bank specific regex patterns
import re # Ensure re is imported

# SBI Bank patterns (Assuming standard, may need review if used)
SBI = {
    'name': 'State Bank of India',
    'header': r"(?i)S\.?\s*No\s+Date\s+Transaction\s+Id\s+Remarks\s+Amount\s+Balance", # Simplified spacing
    'balance': r"^([\d,]+\.\d+\s*\(\w+\))",
    'transaction_pattern': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))\s+([\d,]+\.\d+\s*\(\w+\))(?:\s+.*)?$", # Use \S+ for Txn ID
    'transaction_mapping': {
        'sr_no': 1, 'date': 2, 'transaction_id': 3, 'remarks': 4, 'amount': 5, 'balance': 6
    },
    'transaction_start_pattern': r"^\s*\d+", # Simpler start pattern
    'column_mapping': {
        'sr_no': 'S.No', 'date': 'Date', 'transaction_id': 'Transaction Id', 'remarks': 'Remarks', 'amount': 'Amount(Rs.)', 'balance': 'Balance'
    }
}

# HDFC Bank patterns - MODIFIED FOR BALANCE DIFF APPROACH
HDFC = {
    'name': 'HDFC Bank',
    # Flexible header pattern
    'header': r"(?i)^\s*Date\s+Narration\s+Chq\.\s*[/]\s*Ref\.\s*No\.?\s+Value\s+Dt\s+Withdrawal\s+Amt\.?\s+Deposit\s+Amt\.?\s+Closing\s+Balance\s*",
    'balance_col_name': 'Closing Balance', # Store the name for easy access
    # Group 1: Date, G2: Narration, G3: Ref No (\S+), G4: Value Dt,
    # G5: Amount Block (everything between Value Dt and Balance), G6: Balance (required)
    'transaction_pattern': r"^\s*(\d{2}/\d{2}/\d{2})\s+(.*?)\s+(\S+)\s+(\d{2}/\d{2}/\d{2})\s+(.*?)\s+([\d,]+\.\d{2})\s*$",
    'transaction_start_pattern': r"^\s*\d{2}/\d{2}/\d{2}\s+", # Simpler start, just need date
    'narration_continuation_pattern': r"^\s*(?!(\d{2}/\d{2}/\d{2}\s+|Page\s+No\.:|Account\s+Branch|Address\s*:|City\s*:|State\s*:|Phone\s+no\.|OD\s+Limit|Currency\s*:|Email\s*:|Cust\s+ID|Account\s+No|A/C\s+Open\s+Date|Account\s+Status|RTGS/NEFT\s+IFSC:|MICR:|Product\s+Code:|Branch\s+Code|Nomination:|From:|Date\s+Narration|HDFC\s+BANK|We\s+understand|MR\.|JOINT\s+HOLDERS:|Opening\s+Balance|Statement\s+Summary|TOTAL\s+DEBITS|TOTAL\s+CREDITS|CLOSING\s+BALANCE|Minimum\s+Balance|Average\s+Monthly|Transactions\s+legend:|Interest\s+rate|If\s+you\s+have|Please\s+quote|Regd\.)).*$",
    # Mapping now includes amount_block, withdrawal/deposit are set to None initially
    'transaction_mapping': {
        'date': 1, 'narration': 2, 'ref_no': 3, 'value_dt': 4,
        'amount_block': 5, # Temporary column
        'balance': 6,
        'withdrawal': None, # Will be derived
        'deposit': None     # Will be derived
    },
    'column_mapping': {
        'date': 'Date', 'narration': 'Narration', 'ref_no': 'Chq./Ref.No.', 'value_dt': 'Value Dt',
        'withdrawal': 'Withdrawal Amt.', 'deposit': 'Deposit Amt.', 'balance': 'Closing Balance',
        # Add mappings for derived columns if needed, though they are created dynamically
        'Amount(Rs.)': 'Amount(Rs.)', 'Type': 'Type', 'Amount_Num': 'Amount_Num'
    }
}


# Union Bank patterns - Refined for same-line and multi-line
UNION_BANK = {
    'name': 'Union Bank of India',
    # Flexible header pattern
    'header': r"(?i)S\.?\s*No\s+Date\s+Transaction\s+Id\s+Remarks\s+Amount\s*\(Rs\.\)\s+Balance\s*\(Rs\.\)",
    'balance_col_name': 'Balance(Rs.)', # Store the name for easy access
    'balance': r"([\d,]+\.\d+\s*\(\w+\))", # Generic balance format
    'transaction_pattern_same_line': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))\s+([\d,]+\.\d+\s*\(\w+\))\s*?$",
    'transaction_pattern_multi_line': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))(\s*\(\w+\))?\s*$",
    'transaction_mapping_same_line': {
        'sr_no': 1, 'date': 2, 'transaction_id': 3, 'remarks': 4, 'amount': 5, 'balance': 6
    },
    'transaction_mapping_multi_line': {
        'sr_no': 1, 'date': 2, 'transaction_id': 3, 'remarks': 4, 'amount': 5, 'balance': None
    },
    'transaction_start_pattern': r"^\s*\d+\s+\d{2}/\d{2}/\d{4}",
    'multi_line_balance_pattern': r"^\s*([\d,]+\.\d+\s*\(\w+\))\s*$",
    'remarks_continuation_pattern': r"^\s*(?!(\d+\s+\d{2}/\d{2}/\d{4}|S\.?\s*No.*Date.*Transaction\s+Id|NEFT:|RTGS:|UPI:|INT:|HBPS:|This is system generated|https:|Request to out customers|Registered office:|Details of statement|\(Cr\)|\(Dr\)|Page\s+\d+|Scan the QR code|यूनियन बैंक|Union Bank|VYOM|Account Type|Account Number|Currency|Branch Address|Statement Date|Statement Period|Customer/CIF ID|\s*[\d,]+\.\d+\s*\(\w+\)\s*$)).+$",
    'column_mapping': {
        'sr_no': 'S.No', 'date': 'Date', 'transaction_id': 'Transaction Id', 'remarks': 'Remarks', 'amount': 'Amount(Rs.)', 'balance': 'Balance(Rs.)'
    },
}


# Dictionary to hold all bank configurations
BANKS = {
    "SBI": SBI,
    "HDFC": HDFC,
    "UNION_BANK": UNION_BANK,
}
