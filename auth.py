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
OTP_VALID_SECONDS = 45


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


def register_user(users: dict, username: str, password: str):
    """
    Create a new user with default Checking, Savings, and Credit Card accounts.
    Returns (success: bool, message: str).
    """
    if not username or not password:
        return False, "Username and password cannot be empty."
    if username in users:
        return False, "Username already exists."

    users[username] = {
        "password_hash": hash_password(password),
        "failed_attempts": 0,
        "locked": False,
        "accounts": {
            "checking": {"balance": 0.0},
            "savings": {"balance": 0.0},
            "credit_card": {"limit": 2000.0, "owed": 0.0, "due_date": None},
        },
        "transactions": [],
        "otp": None,
        "otp_expiry": None,
    }
    save_users(users)
    return True, "Account created successfully. You can now log in."


def login_user(users: dict, username: str, password: str):
    """
    Validate credentials, enforcing lockout after MAX_FAILED_ATTEMPTS.
    Returns (success: bool, message: str).
    """
    if username not in users:
        return False, "Invalid username or password."

    user = users[username]

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
