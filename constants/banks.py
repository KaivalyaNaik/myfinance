# Bank specific regex patterns

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
