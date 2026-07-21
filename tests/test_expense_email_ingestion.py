from app.features.expenses.email_ingestion import parse_transaction_email


def email(sender, subject, body, message_id="message-1"):
    return {
        "id": message_id,
        "from": sender,
        "subject": subject,
        "body": body,
        "date": "Fri, 17 Jul 2026 10:30:00 +0530",
    }


def test_major_bank_debit_formats_are_detected():
    samples = [
        email("alerts@hdfcbank.net", "Debit alert", "Rs.1,250.00 has been debited from your account at SWIGGY on 17-Jul."),
        email("alerts@icicibank.com", "Transaction alert", "Your account was debited by INR 899.00 for a purchase at AMAZON."),
        email("alerts@sbi.co.in", "SBI transaction", "INR 500.00 spent using your debit card at UBER."),
        email("alerts@axisbank.com", "Payment alert", "Payment of Rs 2,000.00 to APOLLO PHARMACY was successful."),
        email("alerts@kotak.com", "Purchase alert", "Purchase of INR 349.00 at SPOTIFY completed."),
    ]
    parsed = [parse_transaction_email(item) for item in samples]
    assert all(parsed)
    assert [item["amount"] for item in parsed] == [1250, 899, 500, 2000, 349]
    assert all(item["category"] is None for item in parsed)


def test_non_expenses_are_ignored():
    samples = [
        email("alerts@hdfcbank.net", "OTP", "OTP 123456 for transaction of INR 500."),
        email("alerts@icicibank.com", "Refund", "INR 500 has been refunded and credited."),
        email("alerts@sbi.co.in", "Failed", "Your payment of Rs 500 was unsuccessful."),
        email("shop@example.com", "Order", "Payment of INR 500 completed."),
    ]
    assert all(parse_transaction_email(item) is None for item in samples)


def test_ambiguous_multiple_amounts_are_ignored():
    item = email(
        "alerts@axisbank.com",
        "Debit alert",
        "INR 100 was debited and another transaction of INR 200 was debited.",
    )
    assert parse_transaction_email(item) is None
