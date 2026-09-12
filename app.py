"""
app.py
Main Streamlit entry point for the Virtual Banking System.
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from auth import (
    load_users, save_users, register_user, login_user, generate_otp, verify_otp,
    generate_email_code, verify_email,
)
from accounts import (
    deposit, transfer_own, transfer_other, pay_bill,
    charge_credit_card, pay_credit_card,
    BILL_CATEGORIES, SPEND_CATEGORIES,
)
from analytics import calc_monthly_ratio, spending_by_category, calc_credit_score

st.set_page_config(page_title="Virtual Banking System", page_icon="🏦", layout="wide")

BAND_COLORS = {"red": "#e74c3c", "yellow": "#f1c40f", "green": "#2ecc71"}


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
def init_session():
    defaults = {
        "users": load_users(),
        "logged_in": False,
        "username": None,
        "page": "Dashboard",
        "pending_action": None,   # holds details of an action awaiting OTP
        "otp_stage": False,
        "pending_verification": None,  # username awaiting email confirmation
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh_users():
    """Reload the shared users dict into session state after any write."""
    st.session_state.users = load_users()


# ---------------------------------------------------------------------------
# Login / Registration screen
# ---------------------------------------------------------------------------
def login_screen():
    st.title("🏦 Virtual Banking System")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log In", type="primary"):
            users = load_users()
            success, message = login_user(users, username, password)
            if success:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.users = users
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with tab_register:
        if st.session_state.pending_verification:
            email_confirm_screen()
        else:
            new_username = st.text_input("Choose a username", key="reg_username")
            new_email = st.text_input("Email address", key="reg_email")
            new_phone = st.text_input("Phone number (optional)", key="reg_phone")
            new_address = st.text_input("Home address (optional)", key="reg_address")
            new_password = st.text_input("Choose a password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm password", type="password", key="reg_confirm_password")
            if st.button("Create Account"):
                users = load_users()
                success, message = register_user(
                    users, new_username, new_password, confirm_password, new_email,
                    phone_number=new_phone, address=new_address,
                )
                if success:
                    code = generate_email_code(users, new_username)
                    st.session_state.pending_verification = new_username
                    st.session_state.demo_email_code = code  # demo-only, for on-screen display
                    st.rerun()
                else:
                    st.error(message)


def email_confirm_screen():
    """Simulated email confirmation step shown right after registration."""
    username = st.session_state.pending_verification
    st.info(f"A confirmation code was sent to the email for **{username}**.")
    st.caption(f"Your confirmation code: {st.session_state.demo_email_code} (valid for 5 minutes)")

    entered_code = st.text_input("Enter the 6-digit confirmation code", max_chars=6, key="email_code_input")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Verify Email", type="primary"):
            users = load_users()
            success, message = verify_email(users, username, entered_code)
            if success:
                st.session_state.pending_verification = None
                st.success(message)
            else:
                st.error(message)

    with col2:
        if st.button("Cancel Registration"):
            st.session_state.pending_verification = None
            st.rerun()


# ---------------------------------------------------------------------------
# OTP confirmation screen (shared by every money-moving action)
# ---------------------------------------------------------------------------
def otp_screen():
    st.subheader("🔐 OTP Verification")
    action = st.session_state.pending_action
    st.info(f"Confirm this action: **{action['description']}**")

    demo_otp = st.session_state.users[st.session_state.username]["otp"]
    if demo_otp:
        st.caption(f"Your OTP: {demo_otp} (valid for 90 seconds)")
    else:
        # The previous OTP expired (or was already used) and none has been
        # generated since. Without this branch the app would show "your OTP
        # is None" with no way to recover except cancelling the transaction.
        st.warning("Your previous OTP has expired. Click 'Resend OTP' to get a new one.")

    entered = st.text_input("Enter the 6-digit OTP", max_chars=6)
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Verify OTP", type="primary"):
            # Reload fresh from disk before verifying. verify_otp() saves the
            # whole `users` dict back to disk as part of clearing the OTP, so
            # verifying against a stale cached copy would silently overwrite
            # (and lose) any accounts other people registered in their own
            # sessions since this session last refreshed.
            users = load_users()
            success, message = verify_otp(users, st.session_state.username, entered)
            if success:
                result_success, result_message = action["execute"](users)
                refresh_users()
                st.session_state.pending_action = None
                st.session_state.otp_stage = False
                if result_success:
                    st.success(result_message)
                else:
                    st.error(result_message)
                st.rerun()
            else:
                st.error(message)

    with col2:
        if st.button("Resend OTP"):
            users = load_users()  # fresh, for the same reason as above
            generate_otp(users, st.session_state.username)
            refresh_users()
            st.rerun()

    with col3:
        if st.button("Cancel"):
            st.session_state.pending_action = None
            st.session_state.otp_stage = False
            st.rerun()


def start_otp_flow(description: str, execute_fn):
    """
    Generate an OTP and stage an action for confirmation.
    execute_fn: a function taking `users` dict and returning (bool, str).
    """
    users = load_users()  # fresh, so this save doesn't clobber other users' concurrent changes
    generate_otp(users, st.session_state.username)
    refresh_users()
    st.session_state.pending_action = {"description": description, "execute": execute_fn}
    st.session_state.otp_stage = True
    st.rerun()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def dashboard_page():
    user = st.session_state.users[st.session_state.username]
    st.header("Dashboard")

    col1, col2, col3 = st.columns(3)
    checking = user["accounts"]["checking"]
    savings = user["accounts"]["savings"]
    card = user["accounts"]["credit_card"]
    col1.metric("Checking", f"${checking['balance']:.2f}")
    col1.caption(f"Acct # {checking.get('account_number', 'N/A')}")
    col2.metric("Savings", f"${savings['balance']:.2f}")
    col2.caption(f"Acct # {savings.get('account_number', 'N/A')}")
    col3.metric("Credit Card Owed", f"${card['owed']:.2f}", f"Limit: ${card['limit']:.2f}")
    col3.caption(f"Acct # {card.get('account_number', 'N/A')}")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📊 Monthly Income-to-Spending Ratio")
        ratio_info = calc_monthly_ratio(user["transactions"])
        color = BAND_COLORS[ratio_info["band"]]
        ratio_display = ratio_info["ratio"] if ratio_info["ratio"] is not None else "N/A"
        st.markdown(
            f"""
            <div style="padding:16px;border-radius:10px;background-color:{color}22;
                        border:2px solid {color};">
                <span style="font-size:28px;font-weight:bold;color:{color};">
                    {ratio_display}
                </span><br>
                Income: ${ratio_info['income']:.2f} &nbsp;|&nbsp; Spending: ${ratio_info['spending']:.2f}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        st.subheader("💳 Credit Score")
        score_info = calc_credit_score(user)
        band_color = {
            "Excellent": "#2ecc71", "Good": "#27ae60",
            "Fair": "#f1c40f", "Poor": "#e74c3c",
        }[score_info["band"]]
        st.markdown(
            f"""
            <div style="padding:16px;border-radius:10px;background-color:{band_color}22;
                        border:2px solid {band_color};">
                <span style="font-size:28px;font-weight:bold;color:{band_color};">
                    {score_info['score']}
                </span> — {score_info['band']}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("🧾 Spending by Category (This Month)")
    breakdown = spending_by_category(user["transactions"])
    if breakdown:
        df = pd.DataFrame(list(breakdown.items()), columns=["Category", "Amount"])
        st.bar_chart(df.set_index("Category"))
    else:
        st.caption("No spending recorded yet this month.")


# ---------------------------------------------------------------------------
# Transfer page
# ---------------------------------------------------------------------------
def transfer_page():
    st.header("Transfer Funds")
    user = st.session_state.users[st.session_state.username]

    transfer_type = st.radio("Transfer type", ["Between my own accounts", "To another user"])

    if transfer_type == "Between my own accounts":
        from_acc = st.selectbox("From", ["checking", "savings"], key="own_from")
        to_acc = st.selectbox("To", ["savings", "checking"], key="own_to")
        amount = st.number_input("Amount", min_value=0.0, step=10.0)
        if st.button("Transfer"):
            if from_acc == to_acc:
                st.error("Source and destination accounts must differ.")
            else:
                success, message = transfer_own(st.session_state.users, st.session_state.username,
                                                  from_acc, to_acc, amount)
                refresh_users()
                st.success(message) if success else st.error(message)
                # Same-user transfers don't require OTP per project design

    else:
        recipient = st.text_input("Recipient username")
        amount = st.number_input("Amount", min_value=0.0, step=10.0, key="other_amount")
        if st.button("Continue to OTP"):
            # Reload fresh from disk: other users may have registered in their
            # own sessions since this session's copy of `users` was last loaded,
            # so checking against the stale in-memory copy could wrongly say
            # a real recipient "does not exist".
            current_users = load_users()
            if recipient not in current_users:
                st.error("Recipient does not exist.")
            elif recipient == st.session_state.username:
                st.error("Cannot transfer to yourself using this option.")
            elif amount <= 0:
                st.error("Enter a valid amount.")
            else:
                def execute(users, recipient=recipient, amount=amount):
                    # Reload fresh again at execution time (right after OTP
                    # verification) so the transfer runs against the latest
                    # data on disk instead of whatever was cached when the
                    # OTP screen first opened. otp_screen() reloads session
                    # state from disk again right after this runs, so we
                    # don't need to sync `users` back manually here.
                    fresh_users = load_users()
                    return transfer_other(fresh_users, st.session_state.username, recipient, amount)
                start_otp_flow(f"Transfer ${amount:.2f} to {recipient}", execute)


# ---------------------------------------------------------------------------
# Bill payment page
# ---------------------------------------------------------------------------
def bill_pay_page():
    st.header("Bill Payment")
    category = st.selectbox("Bill type", BILL_CATEGORIES)
    account = st.selectbox("Pay from", ["checking", "savings"])
    amount = st.number_input("Amount", min_value=0.0, step=5.0)

    if st.button("Continue to OTP"):
        if amount <= 0:
            st.error("Enter a valid amount.")
        else:
            def execute(users, category=category, amount=amount, account=account):
                return pay_bill(users, st.session_state.username, category, amount, account)
            start_otp_flow(f"Pay ${amount:.2f} for {category}", execute)


# ---------------------------------------------------------------------------
# Credit card page
# ---------------------------------------------------------------------------
def credit_card_page():
    st.header("Credit Card")
    user = st.session_state.users[st.session_state.username]
    card = user["accounts"]["credit_card"]

    st.metric("Available Credit", f"${card['limit'] - card['owed']:.2f}")
    tab_charge, tab_pay = st.tabs(["Make a Purchase", "Pay Off Balance"])

    with tab_charge:
        category = st.selectbox("Spending category", SPEND_CATEGORIES)
        amount = st.number_input("Purchase amount", min_value=0.0, step=5.0, key="cc_charge_amt")
        if st.button("Continue to OTP", key="cc_charge_btn"):
            if amount <= 0:
                st.error("Enter a valid amount.")
            else:
                def execute(users, category=category, amount=amount):
                    return charge_credit_card(users, st.session_state.username, category, amount)
                start_otp_flow(f"Charge ${amount:.2f} to credit card ({category})", execute)

    with tab_pay:
        from_acc = st.selectbox("Pay from", ["checking", "savings"], key="cc_pay_from")
        amount = st.number_input("Payment amount", min_value=0.0, step=5.0, key="cc_pay_amt")
        if st.button("Continue to OTP", key="cc_pay_btn"):
            if amount <= 0:
                st.error("Enter a valid amount.")
            else:
                def execute(users, from_acc=from_acc, amount=amount):
                    return pay_credit_card(users, st.session_state.username, amount, from_acc)
                start_otp_flow(f"Pay ${amount:.2f} towards credit card", execute)


# ---------------------------------------------------------------------------
# Deposit page
# ---------------------------------------------------------------------------
def deposit_page():
    st.header("Deposit Funds")
    account = st.selectbox("Deposit into", ["checking", "savings"])
    amount = st.number_input("Amount", min_value=0.0, step=10.0)
    if st.button("Deposit"):
        success, message = deposit(st.session_state.users, st.session_state.username, account, amount)
        refresh_users()
        st.success(message) if success else st.error(message)
        # Deposits don't require OTP: no funds are leaving the bank


# ---------------------------------------------------------------------------
# Transaction history page
# ---------------------------------------------------------------------------
def history_page():
    st.header("Transaction History")
    user = st.session_state.users[st.session_state.username]
    transactions = user["transactions"]

    if not transactions:
        st.caption("No transactions yet.")
        return

    df = pd.DataFrame(transactions)
    df = df.sort_values("date", ascending=False)

    type_filter = st.multiselect("Filter by type", sorted(df["type"].unique()), default=None)
    if type_filter:
        df = df[df["type"].isin(type_filter)]

    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Export as CSV", csv, "transaction_history.csv", "text/csv")


# ---------------------------------------------------------------------------
# Profile page
# ---------------------------------------------------------------------------
def profile_page():
    st.header("Profile")
    user = st.session_state.users[st.session_state.username]
    st.write(f"**Username:** {st.session_state.username}")
    st.write(f"**Email:** {user.get('email', 'N/A')}")
    st.write(f"**Phone:** {user.get('phone_number') or 'Not provided'}")
    st.write(f"**Address:** {user.get('address') or 'Not provided'}")
    st.write(f"**Routing Number:** {user.get('routing_number', 'N/A')}")

    st.divider()
    st.subheader("Account Numbers")
    for acc_name in ("checking", "savings", "credit_card"):
        acc_no = user["accounts"][acc_name].get("account_number", "N/A")
        st.write(f"**{acc_name.replace('_', ' ').title()}:** {acc_no}")

    st.divider()
    st.subheader("Change Password")
    old_pw = st.text_input("Current password", type="password")
    new_pw = st.text_input("New password", type="password")
    if st.button("Update Password"):
        from auth import hash_password, save_users
        users = st.session_state.users
        user = users[st.session_state.username]
        if user["password_hash"] != hash_password(old_pw):
            st.error("Current password is incorrect.")
        elif not new_pw:
            st.error("New password cannot be empty.")
        else:
            user["password_hash"] = hash_password(new_pw)
            save_users(users)
            st.success("Password updated successfully.")


# ---------------------------------------------------------------------------
# Main app router
# ---------------------------------------------------------------------------
def main():
    init_session()

    if not st.session_state.logged_in:
        login_screen()
        return

    if st.session_state.otp_stage:
        otp_screen()
        return

    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        page = st.radio("Navigate", [
            "Dashboard", "Transfer", "Bill Payment",
            "Credit Card", "Deposit", "History", "Profile",
        ])
        st.session_state.page = page
        st.divider()
        if st.button("Log Out"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

    pages = {
        "Dashboard": dashboard_page,
        "Transfer": transfer_page,
        "Bill Payment": bill_pay_page,
        "Credit Card": credit_card_page,
        "Deposit": deposit_page,
        "History": history_page,
        "Profile": profile_page,
    }
    pages[st.session_state.page]()


if __name__ == "__main__":
    main()
