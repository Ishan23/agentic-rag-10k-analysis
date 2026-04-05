#!/bin/bash

set -euo pipefail

echo "Setting up the Fireworks AI Agentic RAG take-home environment..."
echo ""

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is not installed."
    echo "Install instructions: https://github.com/astral-sh/uv"
    echo "Quick install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Creating virtual environment..."
uv venv

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing starter dependencies..."
uv pip install -r starter/requirements.txt

valid_pdf_count=$(python - <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, "scripts")

from prepare_data import count_valid_pdfs

print(count_valid_pdfs(Path("data/pdfs")))
PY
)

if [ "$valid_pdf_count" -lt 6 ]; then
    echo "Installing Playwright Chromium browser (needed to render PDFs)..."
    playwright install chromium
fi

echo ""
echo "Preparing assignment data..."
python scripts/prepare_data.py --data-dir data

echo ""
if [ -f "data/financials.db" ]; then
    echo "Found data/financials.db"
else
    echo "Error: data/financials.db is missing after setup."
    exit 1
fi

pdf_count=0
for pdf in data/pdfs/*.pdf; do
    if [ -f "$pdf" ]; then
        pdf_count=$((pdf_count + 1))
    fi
done

if [ "$pdf_count" -eq 6 ]; then
    echo "Found $pdf_count PDF filings under data/pdfs/"
else
    echo "Error: expected 6 PDF filings under data/pdfs/ after setup, found $pdf_count."
    exit 1
fi

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Activate the environment: source .venv/bin/activate"
echo "  2. Inspect the generated data in data/financials.db and data/pdfs/"
echo "  3. Review questions/dev_questions.json"
echo "  4. Review questions/dev_questions_with_answers.json for the public dev answer key"
echo "  5. Copy questions/dev_answers_example.json to dev_answers.json and fill it in"
echo "  6. Build your local agent and verify a reviewer can run it locally"
echo "  7. Build your own evaluation harness using the public dev questions and answers"
