from __future__ import annotations

import argparse
from pathlib import Path

from build_sqlite import create_db
from download_filings import download_and_render_filings
from download_xbrl import download_companyfacts


EXPECTED_PDF_COUNT = 6
MIN_EXPECTED_PDF_PAGES = 20


def count_pdfs(pdf_dir: Path) -> int:
    return len(list(pdf_dir.glob("*.pdf")))


def is_valid_pdf(pdf_path: Path) -> bool:
    if not pdf_path.exists() or pdf_path.stat().st_size < 100_000:
        return False

    try:
        import fitz
    except ImportError:
        return True

    try:
        with fitz.open(pdf_path) as document:
            if document.page_count < MIN_EXPECTED_PDF_PAGES:
                return False

            first_page_text = document.load_page(0).get_text("text").lower()
            if len(first_page_text.strip()) < 300:
                return False
            if "loading inline docs" in first_page_text or "inline viewer" in first_page_text:
                return False
            if "undeclared automated tool" in first_page_text or "please declare your traffic" in first_page_text:
                return False
    except Exception:
        return False

    return True


def count_valid_pdfs(pdf_dir: Path) -> int:
    return sum(1 for pdf_path in pdf_dir.glob("*.pdf") if is_valid_pdf(pdf_path))


def prepare_data(
    *,
    data_dir: Path,
    force: bool = False,
) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = data_dir / "pdfs"
    xbrl_dir = data_dir / "xbrl_raw"
    db_path = data_dir / "financials.db"

    pdf_dir.mkdir(parents=True, exist_ok=True)
    xbrl_dir.mkdir(parents=True, exist_ok=True)

    should_download_xbrl = force or (not db_path.exists() and len(list(xbrl_dir.glob("*_companyfacts.json"))) < 3)
    valid_pdf_count = count_valid_pdfs(pdf_dir)
    should_render_pdfs = force or valid_pdf_count < EXPECTED_PDF_COUNT
    should_build_db = force or not db_path.exists()

    if should_download_xbrl:
        print("Preparing SEC companyfacts data...")
        download_companyfacts(out_dir=xbrl_dir)
    else:
        print("Using existing SEC companyfacts data.")

    if should_render_pdfs:
        print("Rendering 10-K PDF filings...")
        download_and_render_filings(out_dir=pdf_dir)
    else:
        print("Using existing valid 10-K PDF filings.")

    if should_build_db:
        print("Building SQLite database...")
        create_db(xbrl_dir=xbrl_dir, db_path=db_path)
    else:
        print("Using existing SQLite database.")

    pdf_count = count_pdfs(pdf_dir)
    valid_pdf_count = count_valid_pdfs(pdf_dir)
    if pdf_count != EXPECTED_PDF_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_PDF_COUNT} PDF filings, found {pdf_count}")
    if valid_pdf_count != EXPECTED_PDF_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_PDF_COUNT} valid PDF filings, found {valid_pdf_count}")
    if not db_path.exists():
        raise RuntimeError("Expected data/financials.db to exist after preparation")

    print("Data is ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and build the assignment data assets")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory where PDFs, raw XBRL data, and the SQLite database should live",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download and rebuild assets even if they already exist",
    )
    args = parser.parse_args()

    prepare_data(data_dir=Path(args.data_dir), force=args.force)


if __name__ == "__main__":
    main()
