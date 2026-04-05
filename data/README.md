# Data Directory

This directory holds the local data used by the assignment.

Expected contents in the packaged handoff or after setup:

- `financials.db`: the SQLite database used for structured retrieval
- `pdfs/`: the six rendered 10-K filings
- `manifest.json`: a description of the key assignment assets

Optional rebuild-only contents:

- `xbrl_raw/`: intermediate SEC companyfacts JSON used to build the SQLite database. This directory is not included in the packaged handoff, but it may appear if you rebuild the data from SEC sources.

If these assets are missing or the PDFs look invalid, run `./setup.sh` from the extracted project root (the directory that contains `setup.sh`) to fetch and build them. `setup.sh` will reuse existing valid assets and only download raw SEC inputs when it needs to rebuild them.
