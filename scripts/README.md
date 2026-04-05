# Scripts Directory

This directory contains helper scripts for preparing the assignment data.

- `prepare_data.py`: orchestrates assignment data preparation and rebuilds missing assets when needed. It is typically run via `setup.sh`, which also installs the Playwright browser dependency used for PDF rendering.
- `download_xbrl.py`: downloads SEC companyfacts JSON
- `download_filings.py`: renders PDFs from the live SEC filing HTML URLs using Playwright
- `build_sqlite.py`: builds `data/financials.db` from the SEC companyfacts JSON and curated segment data
