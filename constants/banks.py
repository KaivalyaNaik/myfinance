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

# HDFC Bank patterns
HDFC = {
    'name': 'HDFC Bank',
    # Flexible header pattern
    'header': r"(?i)^\s*Date\s+Narration\s+Chq\.\s*[/]\s*Ref\.\s*No\.?\s+Value\s+Dt\s+Withdrawal\s+Amt\.?\s+Deposit\s+Amt\.?\s+Closing\s+Balance\s*",
    'balance': r"([\d,]+\.\d+)$", # Matches closing balance at the end
    # Group 1: Date, Group 2: Narration (part 1), Group 3: Ref No (using \S+), Group 4: Value Dt, Group 5: Withdrawal, Group 6: Deposit, Group 7: Balance
    'transaction_pattern': r"^\s*(\d{2}/\d{2}/\d{2})\s+(.*?)\s+(\S+)\s+(\d{2}/\d{2}/\d{2})\s+([\d,\.]*)\s+([\d,\.]*)\s+([\d,\.]+)\s*$",
    'transaction_start_pattern': r"^\s*\d{2}/\d{2}/\d{2}\s+.*\s+\d{2}/\d{2}/\d{2}\s+[\d,\.]*\s+[\d,\.]*\s+[\d,\.]+\s*$",
    'narration_continuation_pattern': r"^\s*(?!(\d{2}/\d{2}/\d{2}\s+|Page\s+No\.:|Account\s+Branch|Address\s*:|City\s*:|State\s*:|Phone\s+no\.|OD\s+Limit|Currency\s*:|Email\s*:|Cust\s+ID|Account\s+No|A/C\s+Open\s+Date|Account\s+Status|RTGS/NEFT\s+IFSC:|MICR:|Product\s+Code:|Branch\s+Code|Nomination:|From:|Date\s+Narration|HDFC\s+BANK|We\s+understand|MR\.|JOINT\s+HOLDERS:|Opening\s+Balance|Statement\s+Summary|TOTAL\s+DEBITS|TOTAL\s+CREDITS|CLOSING\s+BALANCE|Minimum\s+Balance|Average\s+Monthly|Transactions\s+legend:|Interest\s+rate|If\s+you\s+have|Please\s+quote|Regd\.)).*$",
    'transaction_mapping': {
        'date': 1, 'narration': 2, 'ref_no': 3, 'value_dt': 4, 'withdrawal': 5, 'deposit': 6, 'balance': 7
    },
    'column_mapping': {
        'date': 'Date', 'narration': 'Narration', 'ref_no': 'Chq./Ref.No.', 'value_dt': 'Value Dt', 'withdrawal': 'Withdrawal Amt.', 'deposit': 'Deposit Amt.', 'balance': 'Closing Balance'
    }
}


# Union Bank patterns - Refined for same-line and multi-line
UNION_BANK = {
    'name': 'Union Bank of India',
    # Flexible header pattern
    'header': r"(?i)S\.?\s*No\s+Date\s+Transaction\s+Id\s+Remarks\s+Amount\s*\(Rs\.\)\s+Balance\s*\(Rs\.\)",
    'balance': r"([\d,]+\.\d+\s*\(\w+\))", # Generic balance format

    # Pattern 1: Matches transactions where Balance IS on the same line
    # Group 1: S.No, 2: Date, 3: Txn ID (\S+), 4: Remarks, 5: Amount, 6: Balance
    'transaction_pattern_same_line': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))\s+([\d,]+\.\d+\s*\(\w+\))\s*?$",

    # Pattern 2: Matches transactions where Balance is NOT on the same line (goes up to Amount)
    # Group 1: S.No, 2: Date, 3: Txn ID (\S+), 4: Remarks, 5: Amount, Group 6: Optional trailing (Cr)/(Dr)
    'transaction_pattern_multi_line': r"^\s*(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\S+)\s+(.*?)\s+([\d,]+\.\d+\s*\(\w+\))(\s*\(\w+\))?\s*$",

    # Mapping for Pattern 1 (Same Line)
    'transaction_mapping_same_line': {
        'sr_no': 1, 'date': 2, 'transaction_id': 3, 'remarks': 4, 'amount': 5, 'balance': 6
    },
    # Mapping for Pattern 2 (Multi Line - Balance handled separately)
    'transaction_mapping_multi_line': {
        'sr_no': 1, 'date': 2, 'transaction_id': 3, 'remarks': 4, 'amount': 5, 'balance': None
    },

    # Pattern to identify the start of any potential transaction line
    'transaction_start_pattern': r"^\s*\d+\s+\d{2}/\d{2}/\d{4}",

    # Pattern to find balance specifically when it's on the next line
    'multi_line_balance_pattern': r"^\s*([\d,]+\.\d+\s*\(\w+\))\s*$",

    # Pattern to detect continuation of remarks on subsequent lines.
    'remarks_continuation_pattern': r"^\s*(?!(\d+\s+\d{2}/\d{2}/\d{4}|S\.?\s*No.*Date.*Transaction\s+Id|NEFT:|RTGS:|UPI:|INT:|HBPS:|This is system generated|https:|Request to out customers|Registered office:|Details of statement|\(Cr\)|\(Dr\)|Page\s+\d+|Scan the QR code|यूनियन बैंक|Union Bank|VYOM|Account Type|Account Number|Currency|Branch Address|Statement Date|Statement Period|Customer/CIF ID|\s*[\d,]+\.\d+\s*\(\w+\)\s*$)).+$",

    # Consistent column names for the final DataFrame
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
