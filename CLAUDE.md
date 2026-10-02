# Farm Cashflow Tracker - Project Guidelines

## Project Overview
- **App Name:** Farm Cashflow Tracker
- **Target User:** Small farm owner or farm manager
- **Purpose:** A clean, easy-to-use Streamlit web app to log farm cash inflows (crop sales, livestock sales) and cash outflows/expenditures (seeds, fertilizer, equipment maintenance, labor), and display net cashflow summaries over time.

## Tech Stack & Constraints
- **Language:** Python 3.12
- **Framework:** Streamlit (UI only, no custom HTML/CSS unless requested)
- **Data Storage:** Local CSV file (`cashflow_data.csv`) or SQLite database (`cashflow.db`)
- **Strict Constraint:** Use ONLY pre-installed packages (Streamlit, Pandas, SQLite3). Do NOT attempt to install or import any new third-party packages without explicit permission.

## Development Rules for Claude Code
1. **File Limits:** Keep the project minimal (maximum of 3 code/data files: e.g., `app.py`, `database.py`, and `sample_data.csv`).
2. **Step-by-Step Approval:** Always present a clear plan and explain proposed changes BEFORE editing code. 
3. **No Unrequested Refactoring:** Fix only the bug or build the exact feature requested. Do not rewrite working code unnecessarily.
4. **Data Privacy & Synthetic Data:** 
   - NEVER use real personal names, real company names, phone numbers, or real monetary figures.
   - All sample data must use obvious placeholders (e.g., "Farmer John", "Farm A", "Vendor 1", "Crop Sale #101").

## Command Usage Rules
- Run Streamlit using: `python -m streamlit run app.py`
- Do NOT run commands that delete files or modify directories outside of this project folder.
- Do NOT attempt workaround flags like `--trusted-host` or alter system execution policies/PATH variables.

## Minimum Viable Product (MVP) Scope
1. Input forms to record cash inflows (category, amount, date, description) and outflows (category, amount, date, description).
2. A main dashboard showing total inflows, total expenses, and current net cashflow balance.
3. A simple table displaying recent transactions with filter options (by date or inflow vs. outflow).
4. Must input an option to download a monthly cashflow statement(should be able to dowbload at anytie but for that particular month).
5. Data for past months must still available for comparison.
6. Must show a bar graph to show the spendings and what was spent on.
7. Must calculate profit = Total Inflow - Total Outflow.
8. Must have a provision to show a line chart to compare profits across months

