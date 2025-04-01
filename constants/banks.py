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
    # Stricter regex focusing on mandatory spaces between keywords
    'header': r"(?i)Date.*?Narration.*?Chq.*?Ref.*?No.*?Value.*?Dt.*?Withdrawal.*?Amt.*?Deposit.*?Amt.*?Closing.*?Balance",
    'transaction_pattern': r'''^\s*
        (\d{2}/\d{2}/\d{2})           # Date (Group 1)
        \s+
        (.*?)                         # Narration PART 1 (Group 2) - Non-greedy
        \s+
        (\S+)                         # Ref No (Group 3) - Assume it's the block before Value Date
        \s+
        (\d{2}/\d{2}/\d{2})           # Value Date (Group 4)
        \s+
        (.*?)                         # Everything BETWEEN Value Date and Closing Balance (Group 5)
        \s+
        ([\d,]+\.\d{2})                # Closing Balance (Group 6) - Anchor point!
        \s*
        (.*?)                         # Anything AFTER Closing Balance (Narration PART 2) (Group 7)
    $''',
    'transaction_mapping': {
        'date': 1,
        'narration_part1': 2, # Need to combine later
        'chq_ref_no': 3,
        'value_date': 4,
        'amounts_text': 5,    # Raw text containing amounts
        'closing_balance': 6,
        'narration_part2': 7  # Need to combine later
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
