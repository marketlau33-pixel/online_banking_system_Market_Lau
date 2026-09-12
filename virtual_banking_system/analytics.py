"""
analytics.py
Derives insights from a user's transaction history:
- Monthly income-to-spending ratio (color-banded)
- Spending broken down by category (for charting)
- A simulated credit score, weighted from behavior we already track

All formulas here are intentionally simple and documented so they can be
explained and justified in the project report.
"""

from datetime import datetime
from collections import defaultdict

INCOME_TYPES = {"deposit", "transfer_received"}
SPENDING_TYPES = {"bill_payment", "credit_card_charge", "transfer_own", "transfer_other"}


def _current_month_transactions(transactions):
    now = datetime.now()
    result = []
    for tx in transactions:
        tx_date = datetime.fromisoformat(tx["date"])
        if tx_date.year == now.year and tx_date.month == now.month and tx["status"] == "success":
            result.append(tx)
    return result


def calc_monthly_ratio(transactions):
    """
    Income-to-spending ratio for the current calendar month.
    ratio = total income / total spending

    Bands (as specified for this project):
        ratio < 2        -> "red"    (spending too close to / over income)
        2 <= ratio <= 3   -> "yellow" (acceptable but tight)
        ratio > 3        -> "green"  (healthy buffer)

    Returns dict: {"income": float, "spending": float, "ratio": float or None, "band": str}
    """
    monthly = _current_month_transactions(transactions)
    income = sum(tx["amount"] for tx in monthly if tx["type"] in INCOME_TYPES)
    spending = sum(tx["amount"] for tx in monthly if tx["type"] in SPENDING_TYPES)

    if spending == 0:
        # No spending yet this month: treat as best-case band rather than dividing by zero
        return {"income": income, "spending": spending, "ratio": None, "band": "green"}

    ratio = income / spending
    if ratio < 2:
        band = "red"
    elif ratio <= 3:
        band = "yellow"
    else:
        band = "green"

    return {"income": income, "spending": spending, "ratio": round(ratio, 2), "band": band}


def spending_by_category(transactions):
    """
    Sum successful spending transactions by category, for the current month.
    Returns dict: {category: total_amount}
    """
    monthly = _current_month_transactions(transactions)
    totals = defaultdict(float)
    for tx in monthly:
        if tx["type"] in SPENDING_TYPES:
            totals[tx["category"]] += tx["amount"]
    return dict(totals)


def calc_credit_score(user: dict):
    """
    Simulated credit score, since no real credit bureau data is available.
    Base score of 650, adjusted by four weighted behavioral factors already
    tracked by the system. Bounded to the 300-850 range used by real bureaus.

    Justification for weights (documented for the report):
      - Utilization (35%): the single biggest real-world factor (FICO weights
        it similarly). High utilization signals reliance on credit.
      - Payment history (30%): missed/failed payments are a strong risk signal.
      - Income-to-spending ratio (20%): reflects overall financial discipline
        beyond just the credit card.
      - Account activity (15%): rewards a longer, more established history.
    """
    card = user["accounts"]["credit_card"]
    transactions = user["transactions"]

    score = 650

    # --- Utilization (35%) ---
    limit = card["limit"] if card["limit"] > 0 else 1
    utilization = card["owed"] / limit
    if utilization < 0.3:
        score += 70
    elif utilization < 0.6:
        score += 20
    elif utilization < 0.9:
        score -= 30
    else:
        score -= 70

    # --- Payment history (30%) ---
    payments = [tx for tx in transactions if tx["type"] == "credit_card_payment"]
    failed_payments = [tx for tx in transactions if tx["status"] == "failed"]
    if payments and not failed_payments:
        score += 60
    elif failed_payments and len(failed_payments) <= 2:
        score -= 20
    elif len(failed_payments) > 2:
        score -= 60

    # --- Income-to-spending ratio (20%) ---
    ratio_info = calc_monthly_ratio(transactions)
    if ratio_info["band"] == "green":
        score += 40
    elif ratio_info["band"] == "yellow":
        score += 10
    else:
        score -= 40

    # --- Account activity (15%) ---
    if len(transactions) >= 15:
        score += 30
    elif len(transactions) >= 5:
        score += 10

    score = max(300, min(850, score))

    if score >= 750:
        band = "Excellent"
    elif score >= 670:
        band = "Good"
    elif score >= 580:
        band = "Fair"
    else:
        band = "Poor"

    return {"score": score, "band": band}
