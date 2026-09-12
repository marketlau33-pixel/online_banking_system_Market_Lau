"""
auth.py
Handles user registration, login, account lockout, and OTP generation/verification.
"""

import hashlib
import json
import os
import random
import string
from datetime import datetime, timedelta

DATA_FILE = "users.json"
MAX_FAILED_ATTEMPTS = 3
OTP_VALID_SECONDS = 90
EMAIL_CODE_VALID_SECONDS = 300
ROUTING_NUMBER = "021000089"  # cosmetic: same for every account, like a real bank's routing number


def load_users():
    """Load all user records from the JSON data file."""
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    """Persist all user records back to the JSON data file."""
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=2)


def hash_password(password: str) -> str:
    """Return a SHA-256 hash of the given plaintext password."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_account_number(users: dict, reserved: set = None) -> str:
    """
    Generate a 10-digit account number, checked against existing accounts for
    uniqueness. `reserved` lets a caller avoid collisions with numbers it has
    already generated in the same batch but not yet saved into `users`.
    """
    reserved = reserved or set()
    while True:
        candidate = "".join(random.choices(string.digits, k=10))
        if candidate in reserved:
            continue
        collision = any(
            acc.get("account_number") == candidate
            for u in users.values()
            for acc in u.get("accounts", {}).values()
        )
        if not collision:
            return candidate


def register_user(users: dict, username: str, password: str, confirm_password: str, email: str,
                   phone_number: str = "", address: str = ""):
    """
    Create a new user with default Checking, Savings, and Credit Card accounts.
    The account is created in an unverified state (email_verified=False) and
    cannot log in until the email confirmation code is verified.
    phone_number and address are simulated/cosmetic only; they are not used
    for real verification or communication anywhere in the system.
    Returns (success: bool, message: str).
    """
    if not username or not password or not email:
        return False, "Username, password, and email cannot be empty."
    if username in users:
        return False, "Username already exists."
    if password != confirm_password:
        return False, "Passwords do not match."
    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."

    checking_no = generate_account_number(users)
    savings_no = generate_account_number(users, reserved={checking_no})
    credit_no = generate_account_number(users, reserved={checking_no, savings_no})

    users[username] = {
        "password_hash": hash_password(password),
        "email": email,
        "phone_number": phone_number,
        "address": address,
        "email_verified": False,
        "email_code": None,
        "email_code_expiry": None,
        "failed_attempts": 0,
        "locked": False,
        "routing_number": ROUTING_NUMBER,
        "accounts": {
            "checking": {"balance": 0.0, "account_number": checking_no},
            "savings": {"balance": 0.0, "account_number": savings_no},
            "credit_card": {"limit": 2000.0, "owed": 0.0, "due_date": None,
                             "account_number": credit_no},
        },
        "transactions": [],
        "otp": None,
        "otp_expiry": None,
    }
    save_users(users)
    return True, "Account created. Please verify your email to activate it."


def login_user(users: dict, username: str, password: str):
    """
    Validate credentials, enforcing lockout after MAX_FAILED_ATTEMPTS.
    Returns (success: bool, message: str).
    """
    if username not in users:
        return False, "Invalid username or password."

    user = users[username]

    if not user.get("email_verified", True):
        return False, "Please verify your email before logging in."

    if user.get("locked", False):
        return False, "Account locked due to too many failed attempts. Contact support."

    if user["password_hash"] != hash_password(password):
        user["failed_attempts"] = user.get("failed_attempts", 0) + 1
        if user["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
            user["locked"] = True
            save_users(users)
            return False, "Account locked due to too many failed attempts."
        save_users(users)
        remaining = MAX_FAILED_ATTEMPTS - user["failed_attempts"]
        return False, f"Invalid username or password. {remaining} attempt(s) remaining."

    # Successful login resets the failed attempt counter
    user["failed_attempts"] = 0
    save_users(users)
    return True, "Login successful."


def generate_otp(users: dict, username: str) -> str:
    """Generate a 6-digit OTP for the user, valid for OTP_VALID_SECONDS."""
    otp = "".join(random.choices(string.digits, k=6))
    expiry = (datetime.now() + timedelta(seconds=OTP_VALID_SECONDS)).isoformat()
    users[username]["otp"] = otp
    users[username]["otp_expiry"] = expiry
    save_users(users)
    return otp


def verify_otp(users: dict, username: str, entered_otp: str):
    """
    Check the entered OTP against the stored OTP and its expiry.
    Returns (success: bool, message: str).
    """
    user = users[username]
    stored_otp = user.get("otp")
    expiry_str = user.get("otp_expiry")

    if not stored_otp or not expiry_str:
        return False, "No OTP was generated. Please restart the transaction."

    if datetime.now() > datetime.fromisoformat(expiry_str):
        user["otp"] = None
        user["otp_expiry"] = None
        save_users(users)
        return False, "OTP has expired. Please request a new one."

    if entered_otp != stored_otp:
        return False, "Incorrect OTP. Please try again."

    # OTP consumed after successful use
    user["otp"] = None
    user["otp_expiry"] = None
    save_users(users)
    return True, "OTP verified successfully."


def generate_email_code(users: dict, username: str) -> str:
    """Generate a 6-digit email confirmation code, valid for EMAIL_CODE_VALID_SECONDS."""
    code = "".join(random.choices(string.digits, k=6))
    expiry = (datetime.now() + timedelta(seconds=EMAIL_CODE_VALID_SECONDS)).isoformat()
    users[username]["email_code"] = code
    users[username]["email_code_expiry"] = expiry
    save_users(users)
    return code


def verify_email(users: dict, username: str, entered_code: str):
    """
    Check the entered email confirmation code against the stored code and its expiry.
    On success, marks the account as email_verified so it can log in.
    Returns (success: bool, message: str).
    """
    user = users[username]
    stored_code = user.get("email_code")
    expiry_str = user.get("email_code_expiry")

    if not stored_code or not expiry_str:
        return False, "No confirmation code was generated. Please register again."

    if datetime.now() > datetime.fromisoformat(expiry_str):
        return False, "Confirmation code has expired. Request a new one."

    if entered_code != stored_code:
        return False, "Incorrect confirmation code. Please try again."

    user["email_verified"] = True
    user["email_code"] = None
    user["email_code_expiry"] = None
    save_users(users)
    return True, "Email verified successfully. You can now log in."
