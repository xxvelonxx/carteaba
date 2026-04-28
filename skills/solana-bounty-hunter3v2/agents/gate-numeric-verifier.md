# gate-numeric-verifier

PROFIT CALCULATOR.

TASK:
Calculate attacker profit after fees/slippage.

FORMULA:
profit = stolen_amount - flash_loan_fee - transaction_fees - slippage

OUTPUT: profit > 0 → PASS | profit <= 0 → FAIL
