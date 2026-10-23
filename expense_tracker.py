
"""Expense Tracker: a command-line tool to record and summarize daily spending."""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import date, datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expenses.json")
CATEGORIES = ["food", "transport", "rent", "utilities",
              "entertainment", "shopping", "health", "other"]


class TrackerError(Exception):
    """Raised for any problem the user can fix (bad input, missing ID, broken file)."""


@dataclass
class Expense:
    id: int
    date: str
    amount: int
    category: str
    note: str = ""

# ---------- Validation ----------

def parse_amount(text):
    try:
        amount = int(text)
    except ValueError:
        raise TrackerError(f"Amount must be a whole number of yen, got '{text}'.")
    if amount <= 0:
        raise TrackerError("Amount must be greater than zero.")
    return amount


def parse_category(text):
    category = text.strip().lower()
    if category not in CATEGORIES:
        allowed = ", ".join(CATEGORIES)
        raise TrackerError(f"Unknown category '{text}'. Allowed: {allowed}.")
    return category


def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise TrackerError(f"Date must be a real date in YYYY-MM-DD format, got '{text}'.")


def parse_month(text):
    try:
        return datetime.strptime(text, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        raise TrackerError(f"Month must be in YYYY-MM format, got '{text}'.")


# ---------- Storage ----------

def load_data(path=DATA_FILE):
    if not os.path.exists(path):
        return {"next_id": 1, "expenses": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        expenses = [Expense(**item) for item in raw["expenses"]]
        return {"next_id": raw["next_id"], "expenses": expenses}
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise TrackerError(f"Data file '{path}' is corrupted ({error}). Fix or move it first.")


def save_data(data, path=DATA_FILE):
    raw = {
        "next_id": data["next_id"],
        "expenses": [asdict(e) for e in data["expenses"]],
    }
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)



# ---------- Core logic ----------

def add_expense(data, amount, category, note="", when=None):
    expense = Expense(
        id=data["next_id"],
        date=when or date.today().isoformat(),
        amount=amount,
        category=category,
        note=note,
    )
    data["expenses"].append(expense)
    data["next_id"] += 1
    return expense


def filter_expenses(expenses, month=None, category=None):
    result = []
    for e in expenses:
        if month and not e.date.startswith(month):
            continue
        if category and e.category != category:
            continue
        result.append(e)
    return sorted(result, key=lambda e: (e.date, e.id))


def delete_expense(data, expense_id):
    for index, e in enumerate(data["expenses"]):
        if e.id == expense_id:
            return data["expenses"].pop(index)
    raise TrackerError(f"No expense with ID {expense_id}.")


def summarize(expenses):
    totals = {}
    for e in expenses:
        totals[e.category] = totals.get(e.category, 0) + e.amount
    return sorted(totals.items(), key=lambda pair: pair[1], reverse=True)


# ---------- Output ----------

def yen(amount):
    return f"{amount:,} yen"


def print_table(expenses):
    if not expenses:
        print("No expenses found.")
        return
    print(f"{'ID':>4}  {'Date':<10}  {'Amount':>12}  {'Category':<13}  Note")
    print("-" * 60)
    for e in expenses:
        print(f"{e.id:>4}  {e.date:<10}  {yen(e.amount):>12}  {e.category:<13}  {e.note}")
    print("-" * 60)
    total = sum(e.amount for e in expenses)
    print(f"Total: {yen(total)} across {len(expenses)} expense(s)")


def print_summary(month, expenses, budget=None):
    print(f"Summary for {month}")
    total = sum(e.amount for e in expenses)
    for category, amount in summarize(expenses):
        share = amount / total * 100
        print(f"  {category:<13} {yen(amount):>12}  {share:5.1f}%")
    print(f"  {'TOTAL':<13} {yen(total):>12}")
    if budget is not None:
        remaining = budget - total
        if remaining >= 0:
            print(f"Budget {yen(budget)}: {yen(remaining)} remaining")
        else:
            print(f"Budget {yen(budget)}: OVER by {yen(-remaining)}")


# ---------- Command-line interface ----------

def build_parser():
    parser = argparse.ArgumentParser(description="Track and summarize your daily expenses.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Record a new expense")
    p_add.add_argument("amount", help="Amount in yen, e.g. 850")
    p_add.add_argument("category", help="One of: " + ", ".join(CATEGORIES))
    p_add.add_argument("--note", default="", help="Short description")
    p_add.add_argument("--date", help="Date as YYYY-MM-DD (default: today)")

    p_list = sub.add_parser("list", help="List expenses")
    p_list.add_argument("--month", help="Filter by month, YYYY-MM")
    p_list.add_argument("--category", help="Filter by category")

    p_sum = sub.add_parser("summary", help="Totals per category for one month")
    p_sum.add_argument("--month", help="Month as YYYY-MM (default: this month)")
    p_sum.add_argument("--budget", help="Monthly budget in yen")

    p_del = sub.add_parser("delete", help="Delete an expense by ID")
    p_del.add_argument("id", type=int, help="ID shown by the list command")
    return parser


def run(args):
    data = load_data()
    if args.command == "add":
        when = parse_date(args.date) if args.date else None
        expense = add_expense(data, parse_amount(args.amount),
                              parse_category(args.category), args.note.strip(), when)
        save_data(data)
        print(f"Added expense #{expense.id}: {yen(expense.amount)} ({expense.category})")
    elif args.command == "list":
        month = parse_month(args.month) if args.month else None
        category = parse_category(args.category) if args.category else None
        print_table(filter_expenses(data["expenses"], month, category))
    elif args.command == "summary":
        month = parse_month(args.month) if args.month else date.today().strftime("%Y-%m")
        budget = parse_amount(args.budget) if args.budget else None
        print_summary(month, filter_expenses(data["expenses"], month), budget)
    elif args.command == "delete":
        removed = delete_expense(data, args.id)
        save_data(data)
        print(f"Deleted expense #{removed.id}: {yen(removed.amount)} ({removed.category})")


def main():
    args = build_parser().parse_args()
    try:
        run(args)
    except TrackerError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()