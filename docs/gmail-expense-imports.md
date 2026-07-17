# Gmail transaction expense imports

When Google is connected, Deep Thought checks recent Gmail messages once per
minute for confirmed debit and purchase alerts. A matching expense is inserted
into the local expense database and shown under **Notifications > Imported
expenses**.

Each notification can be kept or deleted. Every expense is temporarily stored
in `misc` and the notification asks the user to choose a category. No merchant
or category mapping is hard-coded. If the user previously categorized the same
merchant, that confirmed choice is displayed as an optional suggestion; it is
never applied automatically.

## Safety and deduplication

- Gmail message IDs prevent the same transaction from being imported twice,
  including after an application restart.
- OTP, refund, reversal, credit, cashback, failed and declined transaction
  messages are ignored.
- Emails with no confirmed debit language or with multiple ambiguous amounts
  are ignored.
- Examined emails are recorded so rejected messages are not downloaded during
  every subsequent scan.
- Gmail content remains local and only the transaction metadata needed by the
  expense tracker is stored.

## Recognized banks

The sender recognizer covers common alerts from HDFC Bank, ICICI Bank, SBI,
Axis Bank, Kotak Mahindra Bank, IndusInd Bank, YES Bank, IDFC FIRST Bank, AU
Small Finance Bank, Federal Bank, Canara Bank, Punjab National Bank, Bank of
Baroda, Union Bank, Indian Bank, RBL Bank, Bandhan Bank, DBS, HSBC, Standard
Chartered, Citi and American Express.

Bank email wording changes over time. The parser deliberately skips uncertain
messages instead of risking an incorrect expense. Additional sanitized sample
formats can be added to `tests/test_expense_email_ingestion.py` before extending
the parser.
