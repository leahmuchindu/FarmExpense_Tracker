import datetime as dt

import pandas as pd
import streamlit as st

import database as db

MIXED = "Mixed Farming"
NEW_CATEGORY = "+ New category"
TYPE_LABELS = {"Inflow": "Income", "Outflow": "Expenditure"}
CURRENCIES = {
    "ZMW": ("K", "Kwacha (K)"),
    "USD": ("$", "US Dollar ($)"),
    "EUR": ("€", "Euro (€)"),
    "GBP": ("£", "British Pound (£)"),
    "ZAR": ("R", "Rand (R)"),
    "KES": ("KSh", "Kenyan Shilling (KSh)"),
    "NGN": ("₦", "Naira (₦)"),
    "INR": ("₹", "Rupee (₹)"),
}
BASE_SYMBOL = CURRENCIES[db.BASE_CURRENCY][0]
SAND_TAN, WARM_BROWN, COFFEE = "#D4A373", "#8B5A3C", "#6F4E37"

st.set_page_config(page_title="Farm Cashflow Tracker", layout="wide")
ss = st.session_state


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Getting today's exchange rates...")
def exchange_rates() -> dict:
    return db.fetch_exchange_rates()


# ---------- Left pane: settings ----------
with st.sidebar:
    st.header("Settings")
    farm_type = st.radio("Farm type", db.FARM_TYPES + [MIXED],
                         captions=[""] * len(db.FARM_TYPES) + ["Combine the farm types you run"])
    is_mixed = farm_type == MIXED
    if is_mixed:
        view_types = st.multiselect("Farm types to combine", db.FARM_TYPES,
                                    default=db.FARM_TYPES[:2], key="mixed_types")
    else:
        view_types = [farm_type]

    currency_code = st.selectbox("Currency", list(CURRENCIES), format_func=lambda c: CURRENCIES[c][1])
    rate = 1.0
    if currency_code != db.BASE_CURRENCY:
        try:
            rates = exchange_rates()
            rate = float(rates["rates"][currency_code])
            st.caption(f"{BASE_SYMBOL} 1 = {CURRENCIES[currency_code][0]} {rate:,.4f} "
                       f"(rate updated {rates['updated'][:16]})")
        except (OSError, ValueError, KeyError):
            st.warning("Couldn't get today's exchange rates, so amounts are shown in Kwacha.")
            currency_code, rate = db.BASE_CURRENCY, 1.0
    st.caption(f"Amounts are entered in Kwacha ({BASE_SYMBOL}).")

if not view_types:
    st.warning("Tick at least one farm type to combine in the left pane.")
    st.stop()

currency = CURRENCIES[currency_code][0]
money_col_format = f"{currency} %.2f"
view_caption = f"{MIXED}: {', '.join(t.replace(' Farming', '') for t in view_types)}" if is_mixed else farm_type


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}{currency} {abs(value):,.2f}"


def base_money(value: float) -> str:
    return f"{BASE_SYMBOL} {value:,.2f}"


def month_label(month: str) -> str:
    return pd.Period(month).strftime("%B %Y")


def this_month() -> str:
    return str(pd.Timestamp.today().to_period("M"))


def short_farm(name: str) -> str:
    return name.replace(" Farming", "")


def record_type_input(key, container=st):
    """In Mixed view each new entry must still be filed under one farm type."""
    if not is_mixed:
        return farm_type
    return container.radio("Record under", view_types, horizontal=True,
                           key=f"{key}_{'_'.join(view_types)}", format_func=short_farm)


def category_input(label, options, key, new_key, container):
    choice = container.selectbox(label, options + [NEW_CATEGORY], key=key)
    if choice == NEW_CATEGORY:
        container.text_input("New category name", key=new_key, placeholder="e.g. Irrigation")


def chosen_category(key, new_key) -> str:
    choice = ss[key]
    return ss.get(new_key, "").strip() if choice == NEW_CATEGORY else choice


def reset_category(key, new_key) -> None:
    if ss.get(key) == NEW_CATEGORY:
        ss.pop(key, None)
    ss[new_key] = ""


# ---------- Load data for the selected view (amounts converted to display currency) ----------
transactions = db.load_transactions()
budgets = db.load_budgets()
transactions["month"] = transactions["date"].dt.strftime("%Y-%m")

df = transactions[transactions["farm_type"].isin(view_types)].copy()
df["amount"] = df["amount"] * rate
farm_budgets = budgets[budgets["farm_type"].isin(view_types)].copy()
farm_budgets["budget_amount"] = farm_budgets["budget_amount"] * rate


def categories_for(types, tx_type) -> list:
    merged = []
    for ft in types:
        for cat in db.get_categories(ft, tx_type, transactions, budgets):
            if cat not in merged:
                merged.append(cat)
    return merged


outflow_categories = categories_for(view_types, "Outflow")
farm_col = {"farm_type": st.column_config.TextColumn("Farm")} if is_mixed else {}
farm_cols = ["farm_type"] if is_mixed else []
money_config = st.column_config.NumberColumn(format=money_col_format)
month_choices = sorted(
    {this_month(), *(str(pd.Period(this_month()) + i) for i in (1, 2)),
     *farm_budgets["month"], *df["month"]},
    reverse=True,
)


def show_transactions(data, newest_first=True):
    columns = ["date"] + farm_cols + ["type", "category", "item", "quantity", "brand", "amount", "description"]
    st.dataframe(
        data.assign(type=data["type"].map(TYPE_LABELS)).sort_values("date", ascending=not newest_first)[columns],
        hide_index=True,
        width="stretch",
        column_config={
            **farm_col,
            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "type": "Type",
            "category": "Category",
            "item": "Item",
            "quantity": "Quantity",
            "brand": "Brand",
            "amount": st.column_config.NumberColumn("Amount", format=money_col_format),
            "description": "Description",
        },
    )


# ---------- Save callbacks (amounts are always saved in Kwacha) ----------
def save_transaction(tx_type, cat_key, record_type):
    category = chosen_category(cat_key, "tx_new_cat")
    amount = ss["tx_amount"]
    item = ss.get("tx_item", "").strip() if tx_type == "Outflow" else ""
    if not category:
        ss["tx_error"] = "Please type a name for the new category."
    elif tx_type == "Outflow" and not item:
        ss["tx_error"] = "Please enter what you bought."
    elif amount <= 0:
        ss["tx_error"] = "Please enter an amount greater than 0."
    else:
        if tx_type == "Outflow":
            db.add_transaction(ss["tx_date"], record_type, tx_type, category, amount,
                               item=item, quantity=ss.get("tx_quantity", ""), brand=ss.get("tx_brand", ""))
        else:
            db.add_transaction(ss["tx_date"], record_type, tx_type, category, amount,
                               description=ss.get("tx_description", ""))
        for key in ("tx_item", "tx_quantity", "tx_brand", "tx_description"):
            ss[key] = ""
        ss["tx_amount"] = 0.0
        reset_category(cat_key, "tx_new_cat")
        ss["flash"] = f"Saved {category}: {base_money(amount)}"


def save_budget(cat_key, record_type):
    category = chosen_category(cat_key, "b_new_cat")
    amount = ss["b_amount"]
    if not category:
        ss["b_error"] = "Please type a name for the new category."
    elif amount <= 0:
        ss["b_error"] = "Please enter a budget amount greater than 0."
    else:
        db.add_budget(ss["b_month"], record_type, category, amount, description=ss.get("b_description", ""))
        ss["b_amount"] = 0.0
        ss["b_description"] = ""
        reset_category(cat_key, "b_new_cat")
        ss["flash"] = f"Added {base_money(amount)} to the {category} budget for {month_label(ss['b_month'])}"


# ---------- Page: profit over time ----------
def profit_page():
    st.title("Profit over time")
    st.caption(f"{view_caption} · amounts in {currency}")
    monthly_profit = (
        df.assign(profit=df["amount"].where(df["type"] == "Inflow", -df["amount"]))
        .groupby("month")["profit"].sum().sort_index()
    )
    if monthly_profit.empty:
        st.info("No transactions yet for this farm type.")
    else:
        st.line_chart(monthly_profit.to_frame("Profit"), x_label="Month", y_label=f"Profit ({currency})",
                      color=COFFEE, height=450)


# ---------- Page: cashflow (dashboard and tabs) ----------
def cashflow_page():
    st.title("Farm Cashflow Tracker")
    st.caption(view_caption)

    total_in = df.loc[df["type"] == "Inflow", "amount"].sum()
    total_out = df.loc[df["type"] == "Outflow", "amount"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Income", money(total_in))
    c2.metric("Total Expenditure", money(total_out))
    c3.metric("Total Profit", money(total_in - total_out))

    budget_tab, transactions_tab, compare_tab, statement_tab = st.tabs(
        ["Budget", "Transactions", "Budget vs Actual", "Monthly Statement"]
    )

    # ----- Budget -----
    with budget_tab:
        if "b_month" not in ss:
            ss["b_month"] = this_month()
        budget_month = st.selectbox("Budget month", month_choices, format_func=month_label, key="b_month")

        st.subheader("Add a budget line")
        b_record = record_type_input("b_record")
        b_cat_key = f"b_cat_{b_record}"
        col_a, col_b, col_c = st.columns(3)
        category_input("Category", db.get_categories(b_record, "Outflow", transactions, budgets),
                       b_cat_key, "b_new_cat", col_a)
        col_b.number_input(f"Budget amount ({BASE_SYMBOL})", min_value=0.0, step=10.0,
                           format="%.2f", key="b_amount")
        col_c.text_input("Description (optional)", key="b_description", placeholder="e.g. Maize seed - Brand A")
        st.button("Add to budget", type="primary", on_click=save_budget, args=(b_cat_key, b_record))
        if "b_error" in ss:
            st.error(ss.pop("b_error"))

        st.subheader(f"Budget lines - {month_label(budget_month)}")
        month_budgets = farm_budgets[farm_budgets["month"] == budget_month]
        if month_budgets.empty:
            st.info("No budget lines for this month yet.")
        else:
            st.dataframe(
                month_budgets[farm_cols + ["category", "description", "budget_amount"]],
                hide_index=True,
                width="stretch",
                column_config={
                    **farm_col,
                    "category": "Category",
                    "description": "Description",
                    "budget_amount": st.column_config.NumberColumn("Amount", format=money_col_format),
                },
            )
            st.markdown(f"Total budget: **{money(month_budgets['budget_amount'].sum())}**")
        st.caption("See how spending compares in the Budget vs Actual tab.")

    # ----- Transactions -----
    with transactions_tab:
        st.subheader("Add a transaction")
        top_left, top_right = st.columns(2)
        tx_type = top_left.radio("Transaction type", ["Inflow", "Outflow"], horizontal=True,
                                 format_func=TYPE_LABELS.get)
        tx_record = record_type_input("tx_record", top_right)
        tx_cat_key = f"tx_cat_{tx_record}_{tx_type}"
        left, right = st.columns(2)
        category_input("Category", db.get_categories(tx_record, tx_type, transactions, budgets),
                       tx_cat_key, "tx_new_cat", left)
        left.date_input("Date", value=dt.date.today(), key="tx_date")
        if tx_type == "Outflow":
            left.text_input("What did you buy?", key="tx_item", placeholder="e.g. Maize Seed")
            right.text_input("Quantity", key="tx_quantity", placeholder="e.g. 3kg")
            right.number_input(f"Price paid (total, {BASE_SYMBOL})", min_value=0.0, step=1.0,
                               format="%.2f", key="tx_amount")
            right.text_input("Brand (optional)", key="tx_brand", placeholder="e.g. Brand A")
        else:
            right.number_input(f"Amount received ({BASE_SYMBOL})", min_value=0.0, step=1.0,
                               format="%.2f", key="tx_amount")
            right.text_input("Description", key="tx_description", placeholder="e.g. Crop Sale #103")
        st.button("Save transaction", type="primary", on_click=save_transaction,
                  args=(tx_type, tx_cat_key, tx_record))
        if "tx_error" in ss:
            st.error(ss.pop("tx_error"))

        st.divider()
        st.subheader("Transaction list")
        if df.empty:
            st.info("No transactions yet for this farm type.")
        else:
            f1, f2 = st.columns(2)
            min_date, max_date = df["date"].min().date(), df["date"].max().date()
            date_range = f1.date_input("Date range", value=(min_date, max_date))
            type_filter = f2.selectbox("Type", ["All", "Inflow", "Outflow"],
                                       format_func=lambda t: TYPE_LABELS.get(t, t))

            view = df
            if len(date_range) == 2:
                start, end = date_range
                view = view[(view["date"].dt.date >= start) & (view["date"].dt.date <= end)]
            if type_filter != "All":
                view = view[view["type"] == type_filter]
            show_transactions(view)

    # ----- Budget vs Actual -----
    with compare_tab:
        compare_month = st.selectbox("Month", month_choices, index=month_choices.index(this_month()),
                                     format_func=month_label, key="ba_month")
        month_budgets = farm_budgets[farm_budgets["month"] == compare_month]
        month_spend = df[(df["type"] == "Outflow") & (df["month"] == compare_month)]
        budget_by_cat = month_budgets.groupby("category")["budget_amount"].sum()
        actual_by_cat = month_spend.groupby("category")["amount"].sum()
        compare = [c for c in outflow_categories if c in budget_by_cat.index or c in actual_by_cat.index]

        st.subheader(f"Budget vs Actual - {month_label(compare_month)}")
        if not compare:
            st.info("Nothing budgeted or spent this month yet.")
        else:
            t1, t2, t3 = st.columns(3)
            t1.metric("Total budgeted", money(budget_by_cat.sum()))
            t2.metric("Total actual", money(actual_by_cat.sum()))
            t3.metric("Remaining", money(budget_by_cat.sum() - actual_by_cat.sum()))

            summary = pd.DataFrame({
                "Category": compare,
                "Budgeted": [float(budget_by_cat.get(c, 0.0)) for c in compare],
                "Actual": [float(actual_by_cat.get(c, 0.0)) for c in compare],
            })
            summary["Status"] = [
                "Not budgeted" if b == 0 else ("Over budget" if a > b else "Within budget")
                for a, b in zip(summary["Actual"], summary["Budgeted"])
            ]
            st.dataframe(summary, hide_index=True, width="stretch",
                         column_config={"Budgeted": money_config, "Actual": money_config})

            over = summary[summary["Status"] == "Over budget"]
            if not over.empty:
                st.warning("Over budget: " + ", ".join(
                    f"{row.Category} by {money(row.Actual - row.Budgeted)}" for row in over.itertuples()))

            st.bar_chart(summary.set_index("Category")[["Budgeted", "Actual"]], horizontal=True,
                         stack=False, color=[SAND_TAN, WARM_BROWN])
            st.caption(f"Amounts in {currency}")

    # ----- Monthly statement -----
    with statement_tab:
        st.subheader("Monthly Statement")
        tx_months = sorted(set(df["month"]), reverse=True)
        if not tx_months:
            st.info("No transactions yet for this farm type.")
        else:
            default = tx_months.index(this_month()) if this_month() in tx_months else 0
            month = st.selectbox("Select month", tx_months, index=default, format_func=month_label, key="s_month")
            month_tx = df[df["month"] == month]
            show_transactions(month_tx, newest_first=False)
            month_income = month_tx.loc[month_tx["type"] == "Inflow", "amount"].sum()
            month_exp = month_tx.loc[month_tx["type"] == "Outflow", "amount"].sum()
            st.markdown(f"Total income: **{money(month_income)}** · Total expenditure: **{money(month_exp)}**")


# ---------- Navigation: links to both pages live in the left pane ----------
cashflow = st.Page(cashflow_page, title="Cashflow", default=True)
profit = st.Page(profit_page, title="Profit over time", url_path="profit")
page = st.navigation([cashflow, profit], position="hidden")

with st.sidebar:
    st.divider()
    st.subheader("Pages")
    st.page_link(cashflow, label="Cashflow")
    st.page_link(profit, label="Profit over time")

if "flash" in ss:
    st.toast(ss.pop("flash"))

page.run()
