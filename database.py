import json
import shutil
import urllib.request
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
CSV_PATH = BASE_DIR / "cashflow_data.csv"
BUDGET_CSV_PATH = BASE_DIR / "budget_data.csv"
SAMPLE_PATH = BASE_DIR / "sample_data.csv"

BASE_CURRENCY = "ZMW"
RATES_URL = "https://open.er-api.com/v6/latest/{base}"

FARM_TYPES = ["Crop Farming", "Livestock Farming", "Poultry Farming", "Aquaculture"]

CATEGORIES = {
    "Crop Farming": {
        "Inflow": ["Crop Sale", "Other Income"],
        "Outflow": ["Seeds", "Fertilizer", "Pesticides", "Equipment Maintenance", "Labor"],
    },
    "Livestock Farming": {
        "Inflow": ["Livestock Sale", "Milk / Eggs / Produce", "Other Income"],
        "Outflow": ["Feed", "Veterinary & Medicine", "Livestock Purchase", "Equipment Maintenance", "Labor"],
    },
    "Poultry Farming": {
        "Inflow": ["Egg Sales", "Bird Sales", "Manure Sales", "Other Income"],
        "Outflow": ["Chicks", "Poultry Feed", "Vaccines & Medicine", "Housing & Equipment",
                    "Litter & Bedding", "Labor"],
    },
    "Aquaculture": {
        "Inflow": ["Fish Sales", "Fingerling Sales", "Other Income"],
        "Outflow": ["Fingerlings", "Fish Feed", "Pond Maintenance", "Water & Aeration",
                    "Nets & Equipment", "Labor"],
    },
}

TRANSACTION_COLUMNS = [
    "date", "farm_type", "type", "category", "item", "quantity", "brand", "amount", "description",
]
BUDGET_COLUMNS = ["month", "farm_type", "category", "description", "budget_amount"]


def load_transactions() -> pd.DataFrame:
    if not CSV_PATH.exists():
        if SAMPLE_PATH.exists():
            shutil.copy(SAMPLE_PATH, CSV_PATH)
        else:
            pd.DataFrame(columns=TRANSACTION_COLUMNS).to_csv(CSV_PATH, index=False)

    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"]).astype(float)
    return df


def add_transaction(date, farm_type, type, category, amount,
                    item="", quantity="", brand="", description="") -> None:
    row = pd.DataFrame([{
        "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
        "farm_type": farm_type,
        "type": type,
        "category": category,
        "item": item.strip(),
        "quantity": quantity.strip(),
        "brand": brand.strip(),
        "amount": round(float(amount), 2),
        "description": description.strip(),
    }], columns=TRANSACTION_COLUMNS)
    row.to_csv(CSV_PATH, mode="a", header=not CSV_PATH.exists(), index=False)


def load_budgets() -> pd.DataFrame:
    if not BUDGET_CSV_PATH.exists():
        pd.DataFrame(columns=BUDGET_COLUMNS).to_csv(BUDGET_CSV_PATH, index=False)

    df = pd.read_csv(BUDGET_CSV_PATH, dtype=str, keep_default_na=False)
    df["budget_amount"] = pd.to_numeric(df["budget_amount"]).astype(float)
    return df


def add_budget(month, farm_type, category, amount, description="") -> None:
    load_budgets()
    row = pd.DataFrame(
        [[month, farm_type, category.strip(), description.strip(), round(float(amount), 2)]],
        columns=BUDGET_COLUMNS,
    )
    row.to_csv(BUDGET_CSV_PATH, mode="a", header=False, index=False)


def fetch_exchange_rates(base=BASE_CURRENCY) -> dict:
    """Returns {"rates": {code: units per 1 base}, "updated": str}; raises OSError/ValueError on failure."""
    with urllib.request.urlopen(RATES_URL.format(base=base), timeout=10) as response:
        data = json.load(response)
    if data.get("result") != "success":
        raise ValueError("Exchange rate service returned an error")
    return {"rates": data["rates"], "updated": data["time_last_update_utc"]}


def get_categories(farm_type, tx_type, transactions, budgets) -> list:
    """Built-in categories first, then any the farmer typed in themselves."""
    categories = list(CATEGORIES[farm_type][tx_type])
    used = transactions.loc[
        (transactions["farm_type"] == farm_type) & (transactions["type"] == tx_type), "category"
    ].tolist()
    if tx_type == "Outflow":
        used += budgets.loc[budgets["farm_type"] == farm_type, "category"].tolist()
    for cat in used:
        if cat and cat not in categories:
            categories.append(cat)
    return categories
