from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
COMPANIES = {
    "AAPL": "CIK0000320193",
    "MSFT": "CIK0000789019",
    "GOOGL": "CIK0001652044",
}
HEADERS = {
    "User-Agent": "Fireworks AI Inc. support@fireworks.ai",
    "Accept-Encoding": "gzip, deflate",
}


def download_companyfacts(out_dir: Path, pause_seconds: float = 0.5) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for ticker, cik in COMPANIES.items():
            url = f"{BASE_URL}/{cik}.json"
            print(f"Downloading {ticker} companyfacts from {url}")
            response = session.get(url, timeout=120)
            response.raise_for_status()

            out_path = out_dir / f"{ticker}_companyfacts.json"
            with out_path.open("w") as file:
                json.dump(response.json(), file, indent=2)

            print(f"  Wrote {out_path}")
            written_paths.append(out_path)
            time.sleep(pause_seconds)

    return written_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Download SEC companyfacts XBRL JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for downloaded JSON files")
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.5,
        help="Pause between SEC requests",
    )
    args = parser.parse_args()

    download_companyfacts(
        out_dir=Path(args.out_dir),
        pause_seconds=args.pause_seconds,
    )


if __name__ == "__main__":
    main()
