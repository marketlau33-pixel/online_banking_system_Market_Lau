# Virtual Banking System

A Streamlit-based simulation of an online banking platform, built for BMCS2713
(Introduction to Python Programming) Final Assessment — Project 1.

## Features

- User registration with email, phone number, and home address (phone/address
  are simulated/cosmetic only — not used for real verification)
- Simulated email confirmation (6-digit code, 5-minute expiry) required before
  a new account can log in
- Password confirmation field on registration, hashed passwords (SHA-256)
- Account lockout after 3 failed login attempts
- OTP verification (6-digit, 90-second expiry, with a Resend OTP option)
  required for money-leaving transactions
- Multi-account support per user: Checking, Savings, and a Credit Card
  (credit line with limit and owed balance, separate from spendable cash)
- Each account has a unique 10-digit account number; every user shares the
  same simulated routing number — both shown on the Dashboard and Profile
- Money transfer: between own accounts (no OTP) and to other users by
  username (OTP required)
- Bill payment across multiple categories
- Credit card purchases (with limit enforcement) and balance payoff
- Deposit functionality
- Full transaction history with filtering and CSV export
- Monthly income-to-spending ratio, color-coded:
  - Red: ratio < 2
  - Yellow: 2 <= ratio <= 3
  - Green: ratio > 3
- Simulated credit score (300-850), derived from credit utilization, payment
  history, income-to-spending ratio, and account activity
- Spending-by-category chart
- Profile page: view contact info and account numbers, change password

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Demo Accounts

Both accounts are pre-verified (email confirmation already completed) so you
can log in immediately.

| Username | Password    |
|----------|-------------|
| alice    | password123 |
| bob      | password123 |

## Project Structure

```
virtual_banking_system/
├── app.py            # Streamlit UI and page routing
├── auth.py           # Registration, login, lockout, OTP
├── accounts.py       # Deposits, transfers, bill pay, credit card ops
├── analytics.py      # Ratio, spending breakdown, credit score
├── users.json         # Persistent data store (auto-created/updated)
└── requirements.txt
```

## Credit Score Formula

Base score of 650, adjusted by four weighted factors:
- **Utilization (35%)** — credit owed relative to limit
- **Payment history (30%)** — on-time vs. failed payments
- **Income-to-spending ratio (20%)** — overall financial discipline
- **Account activity (15%)** — length/volume of transaction history

See `analytics.py` for the exact point weightings and rationale, written to
be cited directly in the project report.

## Note

This is an educational simulation. It does not connect to any real bank,
payment processor, or credit bureau.
