"""
accounts.py
Handles all money-movement operations: deposits, transfers, bill payments,
and credit card charges/payments. Every successful (and failed) action is
logged into the user's transaction history.
"""

from datetime import datetime
from auth import save_users

BILL_CATEGORIES = ["utilities", "subscription", "insurance", "internet", "phone"]
SPEND_CATEGORIES = ["shopping", "dining", "groceries", "transport", "entertainment", "other"]


def _log_transaction(user: dict, tx_type: str, category: str, amount: float,
                      account: str, status: str):
    user["transactions"].append({
        "date": datetime.now().isoformat(),
        "type": tx_type,
        "category": category,
        "amount": amount,
        "account": account,
        "status": status,
    })


def deposit(users: dict, username: str, account: str, amount: float):
    """Add funds to a Checking or Savings account."""
    if amount <= 0:
        return False, "Deposit amount must be greater than zero."

    user = users[username]
    if account not in ("checking", "savings"):
        return False, "Invalid account for deposit."

    user["accounts"][account]["balance"] += amount
    _log_transaction(user, "deposit", "income", amount, account, "success")
    save_users(users)
    return True, f"Deposited {amount:.2f} into {account}."


def transfer_own(users: dict, username: str, from_account: str, to_account: str, amount: float):
    """Transfer between the same user's own Checking/Savings accounts. No OTP required."""
    if amount <= 0:
        return False, "Transfer amount must be greater than zero."
    if from_account == to_account:
        return False, "Source and destination accounts must differ."

    user = users[username]
    if user["accounts"][from_account]["balance"] < amount:
        _log_transaction(user, "transfer_own", "transfer", amount, from_account, "failed")
        save_users(users)
        return False, "Insufficient balance."

    user["accounts"][from_account]["balance"] -= amount
    user["accounts"][to_account]["balance"] += amount
    _log_transaction(user, "transfer_own", "transfer", amount, from_account, "success")
    save_users(users)
    return True, f"Transferred {amount:.2f} from {from_account} to {to_account}."


def transfer_other(users: dict, from_username: str, to_username: str, amount: float,
                    from_account: str = "checking"):
    """
    Transfer funds to another user's Checking account. Caller is responsible
    for requiring OTP verification BEFORE calling this function.
    """
    if amount <= 0:
        return False, "Transfer amount must be greater than zero."
    if to_username not in users:
        return False, "Recipient does not exist."
    if from_username == to_username:
        return False, "Cannot transfer to yourself using this option."

    sender = users[from_username]
    if sender["accounts"][from_account]["balance"] < amount:
        _log_transaction(sender, "transfer_other", "transfer", amount, from_account, "failed")
        save_users(users)
        return False, "Insufficient balance."

    sender["accounts"][from_account]["balance"] -= amount
    users[to_username]["accounts"]["checking"]["balance"] += amount

    _log_transaction(sender, "transfer_other", "transfer", amount, from_account, "success")
    _log_transaction(users[to_username], "transfer_received", "transfer", amount, "checking", "success")
    save_users(users)
    return True, f"Transferred {amount:.2f} to {to_username}."


def pay_bill(users: dict, username: str, category: str, amount: float, account: str = "checking"):
    """Pay a bill (utilities, subscription, etc.) from Checking or Savings."""
    if amount <= 0:
        return False, "Bill amount must be greater than zero."
    if category not in BILL_CATEGORIES:
        return False, "Invalid bill category."

    user = users[username]
    if user["accounts"][account]["balance"] < amount:
        _log_transaction(user, "bill_payment", category, amount, account, "failed")
        save_users(users)
        return False, "Insufficient balance."

    user["accounts"][account]["balance"] -= amount
    _log_transaction(user, "bill_payment", category, amount, account, "success")
    save_users(users)
    return True, f"Paid {amount:.2f} for {category}."


def charge_credit_card(users: dict, username: str, category: str, amount: float):
    """
    Charge a purchase to the credit card. Increases amount owed (a liability),
    does NOT touch checking/savings balances. Blocked if it would exceed the limit.
    """
    if amount <= 0:
        return False, "Charge amount must be greater than zero."
    if category not in SPEND_CATEGORIES:
        return False, "Invalid spending category."

    user = users[username]
    card = user["accounts"]["credit_card"]
    if card["owed"] + amount > card["limit"]:
        _log_transaction(user, "credit_card_charge", category, amount, "credit_card", "failed")
        save_users(users)
        return False, "Charge declined: exceeds available credit limit."

    card["owed"] += amount
    _log_transaction(user, "credit_card_charge", category, amount, "credit_card", "success")
    save_users(users)
    return True, f"Charged {amount:.2f} to credit card for {category}."


def pay_credit_card(users: dict, username: str, amount: float, from_account: str = "checking"):
    """Pay down the credit card balance from Checking or Savings."""
    if amount <= 0:
        return False, "Payment amount must be greater than zero."

    user = users[username]
    card = user["accounts"]["credit_card"]
    payable = min(amount, card["owed"])

    if user["accounts"][from_account]["balance"] < payable:
        _log_transaction(user, "credit_card_payment", "credit_payment", amount, from_account, "failed")
        save_users(users)
        return False, "Insufficient balance to make this payment."

    user["accounts"][from_account]["balance"] -= payable
    card["owed"] -= payable
    _log_transaction(user, "credit_card_payment", "credit_payment", payable, from_account, "success")
    save_users(users)
    return True, f"Paid {payable:.2f} towards credit card balance."
