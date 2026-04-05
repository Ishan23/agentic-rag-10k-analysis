from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from playwright.sync_api import sync_playwright


FILINGS = [
    {
        "ticker": "AAPL",
        "year": "FY2024",
        "form": "10-K",
        "url": "https://www.sec.gov/Archives/edgar/data/0000320193/000032019324000123/aapl-20240928.htm",
    },
    {
        "ticker": "AAPL",
        "year": "FY2025",
        "form": "10-K",
        "url": "https://www.sec.gov/Archives/edgar/data/0000320193/000032019325000079/aapl-20250927.htm",
    },
    {
        "ticker": "GOOGL",
        "year": "FY2024",
        "form": "10-K",
        "url": "https://www.sec.gov/Archives/edgar/data/0001652044/000165204425000014/goog-20241231.htm",
    },
    {
        "ticker": "GOOGL",
        "year": "FY2025",
        "form": "10-K",
        "url": "https://www.sec.gov/Archives/edgar/data/0001652044/000165204426000018/goog-20251231.htm",
    },
    {
        "ticker": "MSFT",
        "year": "FY2024",
        "form": "10-K",
        "url": "https://www.sec.gov/Archives/edgar/data/0000789019/000095017024087843/msft-20240630.htm",
    },
    {
        "ticker": "MSFT",
        "year": "FY2025",
        "form": "10-K",
        "url": "https://www.sec.gov/Archives/edgar/data/0000789019/000095017025100235/msft-20250630.htm",
    },
]
SEC_HEADERS = {
    "User-Agent": "Fireworks AI Inc. support@fireworks.ai",
    "Accept-Encoding": "gzip, deflate",
}

OVERRIDE_CSS = """\
<style>
* {
    page-break-before: auto !important;
    page-break-after: auto !important;
    break-before: auto !important;
    break-after: auto !important;
}
</style>
"""

IMG_SRC_PATTERN = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*["\'])([^"\']+)(["\'])', re.IGNORECASE)


def sec_get(url: str, session: requests.Session) -> requests.Response:
    response = session.get(url, timeout=120)
    response.raise_for_status()
    if "Your Request Originates from an Undeclared Automated Tool" in response.text:
        raise RuntimeError(
            f"SEC blocked the request for {url}. " "Wait a few minutes and retry, or use a different network."
        )
    return response


def fetch_image_as_data_uri(url: str, session: requests.Session) -> str | None:
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception:
        return None

    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
    if not content_type:
        content_type = mimetypes.guess_type(url)[0] or "image/png"

    encoded = base64.b64encode(resp.content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def inline_images(html: str, base_url: str, session: requests.Session) -> str:
    seen: dict[str, str | None] = {}

    def replace_src(match: re.Match) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)

        if src.startswith("data:"):
            return match.group(0)

        absolute_url = urljoin(base_url, src)

        if absolute_url not in seen:
            seen[absolute_url] = fetch_image_as_data_uri(absolute_url, session)

        data_uri = seen[absolute_url]
        if data_uri:
            return f"{prefix}{data_uri}{suffix}"
        return match.group(0)

    return IMG_SRC_PATTERN.sub(replace_src, html)


def prepare_html(html: str, filing_url: str, session: requests.Session) -> str:
    html = inline_images(html, base_url=filing_url, session=session)

    if "</head>" in html:
        html = html.replace("</head>", OVERRIDE_CSS + "</head>", 1)
    else:
        html = OVERRIDE_CSS + html

    return html


def render_html_to_pdf(*, page, html: str, pdf_path: Path) -> None:
    pdf_path.unlink(missing_ok=True)
    page.set_content(html, wait_until="load", timeout=120_000)
    page.pdf(
        path=str(pdf_path),
        format="Letter",
        display_header_footer=False,
        print_background=True,
        margin={"top": "0.4in", "bottom": "0.4in", "left": "0.5in", "right": "0.5in"},
    )


def download_and_render_filings(
    out_dir: Path,
    pause_seconds: float = 2.0,
    **_kwargs,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    for stale in list(out_dir.glob("*.tmp.pdf")):
        stale.unlink(missing_ok=True)

    prepared: list[tuple[dict, str]] = []

    with requests.Session() as session:
        session.headers.update(SEC_HEADERS)

        for filing in FILINGS:
            stem = f"{filing['ticker']}_{filing['year']}_{filing['form']}"
            print(f"Downloading {stem} HTML and images from SEC")
            resp = sec_get(filing["url"], session)
            html = prepare_html(resp.text, filing_url=filing["url"], session=session)
            prepared.append((filing, html))
            time.sleep(pause_seconds)

    written_pdfs: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        for filing, html in prepared:
            stem = f"{filing['ticker']}_{filing['year']}_{filing['form']}"
            pdf_path = out_dir / f"{stem}.pdf"

            print(f"Rendering {stem} PDF")
            render_html_to_pdf(page=page, html=html, pdf_path=pdf_path)
            written_pdfs.append(pdf_path)

        browser.close()

    return written_pdfs


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and render SEC filing PDFs")
    parser.add_argument("--out-dir", required=True, help="Directory for PDF outputs")
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Pause between SEC download requests",
    )
    args = parser.parse_args()

    download_and_render_filings(
        out_dir=Path(args.out_dir),
        pause_seconds=args.pause_seconds,
    )


if __name__ == "__main__":
    main()
