from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


COMPANIES = {
    "AAPL": {
        "name": "Apple Inc.",
        "cik": "0000320193",
        "sic": "3571",
        "sector": "Technology",
        "fiscal_year_end": "September",
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "cik": "0000789019",
        "sic": "7372",
        "sector": "Technology",
        "fiscal_year_end": "June",
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "cik": "0001652044",
        "sic": "7372",
        "sector": "Technology",
        "fiscal_year_end": "December",
    },
}

INCOME_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "cost_of_revenue": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "eps_basic": ["EarningsPerShareBasic"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "research_and_development": ["ResearchAndDevelopmentExpense"],
    "total_operating_expenses": ["OperatingExpenses", "CostsAndExpenses"],
}

BALANCE_CONCEPTS = {
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": ["StockholdersEquity"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
    ],
    "total_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "short_term_debt": ["ShortTermBorrowings", "CommercialPaper"],
    "accounts_receivable": ["AccountsReceivableNetCurrent"],
    "total_current_assets": ["AssetsCurrent"],
    "total_current_liabilities": ["LiabilitiesCurrent"],
}

# Segment revenue data verified against PDF filings.
# MSFT uses the restated segment definitions from its FY2025 10-K.
# GOOGL reports hedging gains (losses) as a reconciliation between segment
# totals and consolidated revenue. These rows ensure SUM(segment_revenue)
# matches income_statements.revenue for all companies.
SEGMENT_REVENUE = [
    ("AAPL", "2023-09-30", "FY", "iPhone", 200_583_000_000),
    ("AAPL", "2023-09-30", "FY", "Mac", 29_357_000_000),
    ("AAPL", "2023-09-30", "FY", "iPad", 28_300_000_000),
    ("AAPL", "2023-09-30", "FY", "Wearables, Home and Accessories", 39_845_000_000),
    ("AAPL", "2023-09-30", "FY", "Services", 85_200_000_000),
    ("AAPL", "2024-09-28", "FY", "iPhone", 201_183_000_000),
    ("AAPL", "2024-09-28", "FY", "Mac", 29_984_000_000),
    ("AAPL", "2024-09-28", "FY", "iPad", 26_694_000_000),
    ("AAPL", "2024-09-28", "FY", "Wearables, Home and Accessories", 37_005_000_000),
    ("AAPL", "2024-09-28", "FY", "Services", 96_169_000_000),
    ("AAPL", "2025-09-27", "FY", "iPhone", 209_586_000_000),
    ("AAPL", "2025-09-27", "FY", "Mac", 33_708_000_000),
    ("AAPL", "2025-09-27", "FY", "iPad", 28_023_000_000),
    ("AAPL", "2025-09-27", "FY", "Wearables, Home and Accessories", 35_686_000_000),
    ("AAPL", "2025-09-27", "FY", "Services", 109_158_000_000),
    ("MSFT", "2023-06-30", "FY", "Productivity and Business Processes", 94_151_000_000),
    ("MSFT", "2023-06-30", "FY", "Intelligent Cloud", 72_944_000_000),
    ("MSFT", "2023-06-30", "FY", "More Personal Computing", 44_820_000_000),
    ("MSFT", "2024-06-30", "FY", "Productivity and Business Processes", 106_820_000_000),
    ("MSFT", "2024-06-30", "FY", "Intelligent Cloud", 87_464_000_000),
    ("MSFT", "2024-06-30", "FY", "More Personal Computing", 50_838_000_000),
    ("MSFT", "2025-06-30", "FY", "Productivity and Business Processes", 120_810_000_000),
    ("MSFT", "2025-06-30", "FY", "Intelligent Cloud", 106_265_000_000),
    ("MSFT", "2025-06-30", "FY", "More Personal Computing", 54_649_000_000),
    ("GOOGL", "2023-12-31", "FY", "Google Services", 272_543_000_000),
    ("GOOGL", "2023-12-31", "FY", "Google Cloud", 33_088_000_000),
    ("GOOGL", "2023-12-31", "FY", "Other Bets", 1_527_000_000),
    ("GOOGL", "2024-12-31", "FY", "Google Services", 304_930_000_000),
    ("GOOGL", "2024-12-31", "FY", "Google Cloud", 43_229_000_000),
    ("GOOGL", "2024-12-31", "FY", "Other Bets", 1_648_000_000),
    ("GOOGL", "2025-12-31", "FY", "Google Services", 342_721_000_000),
    ("GOOGL", "2025-12-31", "FY", "Google Cloud", 58_705_000_000),
    ("GOOGL", "2025-12-31", "FY", "Other Bets", 1_537_000_000),
    ("GOOGL", "2023-12-31", "FY", "Hedging gains (losses)", 236_000_000),
    ("GOOGL", "2024-12-31", "FY", "Hedging gains (losses)", 211_000_000),
    ("GOOGL", "2025-12-31", "FY", "Hedging gains (losses)", -127_000_000),
]

GEOGRAPHIC_REVENUE = [
    ("AAPL", "2023-09-30", "FY", "Americas", 162_560_000_000),
    ("AAPL", "2023-09-30", "FY", "Europe", 94_294_000_000),
    ("AAPL", "2023-09-30", "FY", "Greater China", 72_559_000_000),
    ("AAPL", "2023-09-30", "FY", "Japan", 24_257_000_000),
    ("AAPL", "2023-09-30", "FY", "Rest of Asia Pacific", 29_615_000_000),
    ("AAPL", "2024-09-28", "FY", "Americas", 167_045_000_000),
    ("AAPL", "2024-09-28", "FY", "Europe", 101_328_000_000),
    ("AAPL", "2024-09-28", "FY", "Greater China", 66_952_000_000),
    ("AAPL", "2024-09-28", "FY", "Japan", 25_052_000_000),
    ("AAPL", "2024-09-28", "FY", "Rest of Asia Pacific", 30_658_000_000),
    ("AAPL", "2025-09-27", "FY", "Americas", 178_353_000_000),
    ("AAPL", "2025-09-27", "FY", "Europe", 111_032_000_000),
    ("AAPL", "2025-09-27", "FY", "Greater China", 64_377_000_000),
    ("AAPL", "2025-09-27", "FY", "Japan", 28_703_000_000),
    ("AAPL", "2025-09-27", "FY", "Rest of Asia Pacific", 33_696_000_000),
    ("MSFT", "2023-06-30", "FY", "United States", 106_744_000_000),
    ("MSFT", "2023-06-30", "FY", "Other countries", 105_171_000_000),
    ("MSFT", "2024-06-30", "FY", "United States", 124_704_000_000),
    ("MSFT", "2024-06-30", "FY", "Other countries", 120_418_000_000),
    ("MSFT", "2025-06-30", "FY", "United States", 144_546_000_000),
    ("MSFT", "2025-06-30", "FY", "Other countries", 137_178_000_000),
    ("GOOGL", "2023-12-31", "FY", "United States", 146_286_000_000),
    ("GOOGL", "2023-12-31", "FY", "EMEA", 91_038_000_000),
    ("GOOGL", "2023-12-31", "FY", "APAC", 51_514_000_000),
    ("GOOGL", "2023-12-31", "FY", "Other Americas", 18_320_000_000),
    ("GOOGL", "2024-12-31", "FY", "United States", 170_447_000_000),
    ("GOOGL", "2024-12-31", "FY", "EMEA", 102_127_000_000),
    ("GOOGL", "2024-12-31", "FY", "APAC", 56_815_000_000),
    ("GOOGL", "2024-12-31", "FY", "Other Americas", 20_418_000_000),
    ("GOOGL", "2025-12-31", "FY", "United States", 194_229_000_000),
    ("GOOGL", "2025-12-31", "FY", "EMEA", 117_152_000_000),
    ("GOOGL", "2025-12-31", "FY", "APAC", 67_680_000_000),
    ("GOOGL", "2025-12-31", "FY", "Other Americas", 23_902_000_000),
    ("GOOGL", "2023-12-31", "FY", "Hedging gains (losses)", 236_000_000),
    ("GOOGL", "2024-12-31", "FY", "Hedging gains (losses)", 211_000_000),
    ("GOOGL", "2025-12-31", "FY", "Hedging gains (losses)", -127_000_000),
]


def load_xbrl(xbrl_dir: Path, ticker: str) -> dict:
    path = xbrl_dir / f"{ticker}_companyfacts.json"
    with path.open() as file:
        return json.load(file)


def get_concept_values(
    usgaap: dict,
    concept_names: list[str],
    form_filter: str = "10-K",
) -> list[dict]:
    collected: list[dict] = []
    for priority, concept_name in enumerate(concept_names):
        if concept_name not in usgaap:
            continue

        units = usgaap[concept_name].get("units", {})
        unit_key = "USD" if "USD" in units else ("USD/shares" if "USD/shares" in units else None)
        if unit_key is None:
            continue

        for value in units[unit_key]:
            if form_filter and value.get("form") != form_filter:
                continue

            row = dict(value)
            row["_concept"] = concept_name
            row["_priority"] = priority
            collected.append(row)

    return collected


def is_annual_period(start_str: str | None, end_str: str | None) -> bool:
    try:
        start = datetime.strptime(start_str or "", "%Y-%m-%d")
        end = datetime.strptime(end_str or "", "%Y-%m-%d")
    except ValueError:
        return False

    days = (end - start).days
    return 350 <= days <= 380


def extract_annual_income(usgaap: dict, target_period_end_years: set[int]) -> list[dict]:
    results: dict[tuple[str, str], dict] = {}

    for field, concepts in INCOME_CONCEPTS.items():
        for value in get_concept_values(usgaap, concepts):
            if "start" not in value:
                continue
            if not is_annual_period(value.get("start"), value.get("end")):
                continue
            if value.get("val") is None:
                continue

            period_end = value.get("end")
            if not period_end:
                continue

            period_end_year = int(period_end[:4])
            if period_end_year not in target_period_end_years:
                continue

            key = (field, period_end)
            filed = value.get("filed", "")
            if (
                key not in results
                or value["_priority"] < results[key]["_priority"]
                or (value["_priority"] == results[key]["_priority"] and filed > results[key]["filed"])
            ):
                results[key] = {
                    "field": field,
                    "period_start": value.get("start"),
                    "period_end": period_end,
                    "value": value["val"],
                    "fy": period_end_year,
                    "filed": filed,
                    "concept": value["_concept"],
                    "_priority": value["_priority"],
                }

    return list(results.values())


def extract_balance_sheet(usgaap: dict, target_period_end_years: set[int]) -> list[dict]:
    results: dict[tuple[str, str], dict] = {}

    for field, concepts in BALANCE_CONCEPTS.items():
        for value in get_concept_values(usgaap, concepts):
            period_end = value.get("end")
            if not period_end:
                continue
            if value.get("fp") != "FY":
                continue
            if value.get("val") is None:
                continue

            period_end_year = int(period_end[:4])
            if period_end_year not in target_period_end_years:
                continue

            key = (field, period_end)
            filed = value.get("filed", "")
            if (
                key not in results
                or value["_priority"] < results[key]["_priority"]
                or (value["_priority"] == results[key]["_priority"] and filed > results[key]["filed"])
            ):
                results[key] = {
                    "field": field,
                    "period_end": period_end,
                    "value": value["val"],
                    "fy": period_end_year,
                    "filed": filed,
                    "concept": value["_concept"],
                    "_priority": value["_priority"],
                }

    return list(results.values())


def create_db(xbrl_dir: Path, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE companies (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cik TEXT NOT NULL,
            sic TEXT,
            sector TEXT,
            fiscal_year_end TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE income_statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_ticker TEXT NOT NULL REFERENCES companies(ticker),
            fiscal_year INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            period_type TEXT NOT NULL,
            revenue BIGINT,
            cost_of_revenue BIGINT,
            gross_profit BIGINT,
            research_and_development BIGINT,
            total_operating_expenses BIGINT,
            operating_income BIGINT,
            net_income BIGINT,
            eps_basic REAL,
            eps_diluted REAL,
            UNIQUE(company_ticker, period_end, period_type)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE balance_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_ticker TEXT NOT NULL REFERENCES companies(ticker),
            fiscal_year INTEGER NOT NULL,
            period_end TEXT NOT NULL,
            period_type TEXT NOT NULL,
            total_assets BIGINT,
            total_liabilities BIGINT,
            stockholders_equity BIGINT,
            cash_and_equivalents BIGINT,
            total_debt BIGINT,
            short_term_debt BIGINT,
            accounts_receivable BIGINT,
            total_current_assets BIGINT,
            total_current_liabilities BIGINT,
            UNIQUE(company_ticker, period_end, period_type)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE segment_revenue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_ticker TEXT NOT NULL REFERENCES companies(ticker),
            fiscal_year INTEGER NOT NULL,
            period_end TEXT NOT NULL,
            period_type TEXT NOT NULL,
            segment_name TEXT NOT NULL,
            revenue BIGINT NOT NULL,
            UNIQUE(company_ticker, period_end, period_type, segment_name)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE geographic_revenue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_ticker TEXT NOT NULL REFERENCES companies(ticker),
            fiscal_year INTEGER NOT NULL,
            period_end TEXT NOT NULL,
            period_type TEXT NOT NULL,
            region TEXT NOT NULL,
            revenue BIGINT NOT NULL,
            UNIQUE(company_ticker, period_end, period_type, region)
        )
        """
    )

    for ticker, info in COMPANIES.items():
        cursor.execute(
            "INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?)",
            (
                ticker,
                info["name"],
                info["cik"],
                info["sic"],
                info["sector"],
                info["fiscal_year_end"],
            ),
        )

    target_period_end_years = {2023, 2024, 2025}
    for ticker in COMPANIES:
        data = load_xbrl(xbrl_dir=xbrl_dir, ticker=ticker)
        usgaap = data["facts"]["us-gaap"]

        income_entries = extract_annual_income(
            usgaap=usgaap,
            target_period_end_years=target_period_end_years,
        )
        income_by_period: dict[str, dict] = {}
        for entry in income_entries:
            period_end = entry["period_end"]
            if period_end not in income_by_period:
                income_by_period[period_end] = {
                    "period_start": entry["period_start"],
                    "period_end": period_end,
                    "fy": entry["fy"],
                }
            income_by_period[period_end][entry["field"]] = entry["value"]

        for period_end, row in income_by_period.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO income_statements (
                    company_ticker,
                    fiscal_year,
                    period_start,
                    period_end,
                    period_type,
                    revenue,
                    cost_of_revenue,
                    gross_profit,
                    research_and_development,
                    total_operating_expenses,
                    operating_income,
                    net_income,
                    eps_basic,
                    eps_diluted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    row["fy"],
                    row.get("period_start"),
                    period_end,
                    "FY",
                    row.get("revenue"),
                    row.get("cost_of_revenue"),
                    row.get("gross_profit"),
                    row.get("research_and_development"),
                    row.get("total_operating_expenses"),
                    row.get("operating_income"),
                    row.get("net_income"),
                    row.get("eps_basic"),
                    row.get("eps_diluted"),
                ),
            )

        balance_entries = extract_balance_sheet(
            usgaap=usgaap,
            target_period_end_years=target_period_end_years,
        )
        balance_by_period: dict[str, dict] = {}
        for entry in balance_entries:
            period_end = entry["period_end"]
            if period_end not in balance_by_period:
                balance_by_period[period_end] = {"period_end": period_end, "fy": entry["fy"]}
            balance_by_period[period_end][entry["field"]] = entry["value"]

        for period_end, row in balance_by_period.items():
            cursor.execute(
                """
                INSERT OR IGNORE INTO balance_sheets (
                    company_ticker,
                    fiscal_year,
                    period_end,
                    period_type,
                    total_assets,
                    total_liabilities,
                    stockholders_equity,
                    cash_and_equivalents,
                    total_debt,
                    short_term_debt,
                    accounts_receivable,
                    total_current_assets,
                    total_current_liabilities
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker,
                    row["fy"],
                    period_end,
                    "FY",
                    row.get("total_assets"),
                    row.get("total_liabilities"),
                    row.get("stockholders_equity"),
                    row.get("cash_and_equivalents"),
                    row.get("total_debt"),
                    row.get("short_term_debt"),
                    row.get("accounts_receivable"),
                    row.get("total_current_assets"),
                    row.get("total_current_liabilities"),
                ),
            )

    for ticker, period_end, period_type, segment_name, revenue in SEGMENT_REVENUE:
        fiscal_year = int(period_end[:4])
        cursor.execute(
            "INSERT OR IGNORE INTO segment_revenue VALUES (NULL, ?, ?, ?, ?, ?, ?)",
            (ticker, fiscal_year, period_end, period_type, segment_name, revenue),
        )

    for ticker, period_end, period_type, region, revenue in GEOGRAPHIC_REVENUE:
        fiscal_year = int(period_end[:4])
        cursor.execute(
            "INSERT OR IGNORE INTO geographic_revenue VALUES (NULL, ?, ?, ?, ?, ?, ?)",
            (ticker, fiscal_year, period_end, period_type, region, revenue),
        )

    conn.commit()

    for table in (
        "companies",
        "income_statements",
        "balance_sheets",
        "segment_revenue",
        "geographic_revenue",
    ):
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")

    conn.close()
    print(f"Database written to {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build financials.db from SEC companyfacts JSON")
    parser.add_argument("--xbrl-dir", required=True, help="Directory containing companyfacts JSON")
    parser.add_argument("--db-path", required=True, help="Output SQLite database path")
    args = parser.parse_args()

    create_db(
        xbrl_dir=Path(args.xbrl_dir),
        db_path=Path(args.db_path),
    )


if __name__ == "__main__":
    main()
