# Fireworks AI AMLE Take-Home: Agentic RAG for 10-K Analysis

## 🚀 How to Run the Submission
1. **Setup Environment**: Ensure your `.env` file contains a valid `FIREWORKS_API_KEY`. Run `./setup.sh` to install dependencies and initialize the vector embeddings and SQLite database.
2. **Start the Server**: Boot the agentic backend by running `python main.py` in your terminal. This exposes the core API at `http://localhost:8000/api/chat`.
3. **Access the Interactive Web UI**: Open your web browser and navigate to `http://localhost:8000`. You will interact seamlessly with the built-in conversational client.
4. **Run the Evaluations**: While the server is running, execute `python evaluate.py` in a new terminal tab to run an automated evaluation pass. Additionally, you can inspect `dev_answers.json` in this root directory to see the absolute highest scoring batch outputs!
5. **Read the Report**: Please see the `REPORT.md` file located in the root directory for a comprehensive breakdown of the system architecture, evaluation results, and architectural tradeoffs.

---

This take-home is meant to mirror part of the Applied Machine Learning Engineer role: supporting customers in their journey to build GenAI applications on Fireworks.

In this exercise, you should approach the problem like a Fireworks engineer supporting a customer who needs an agentic RAG workflow over structured financial data and 10-K filings.

## What We're Looking For

1. Customer-oriented problem solving: translate the customer's needs into a practical system design.
2. Agent and tool design: decide when to query SQL, search PDFs, or combine both.
3. Evaluation discipline: show how you measured quality and where the system still fails.
4. Practical trade-offs: explain choices around models, latency, cost, reliability, and complexity.
5. Communication: provide clear instructions, clear answers, and a concise technical report.

## Customer Scenario

**From:** Natalie Brooks <natalie.brooks@acmecorp.example.com>  
**To:** Solutions Team <solutions@fireworks.ai>  
**Subject:** Help Needed: Local Research Assistant for 10-K Analysis

Hi Fireworks team,

Our research team spends a lot of time reading annual reports, cross-checking management commentary against financial tables, and building simple comparisons across companies. We have a local dataset that combines structured financial data with the original 10-K filings, and we want a local AI assistant that can help analysts answer increasingly complex questions over that material.

Our current prototype can handle simple lookups, but it breaks down when a question requires planning, multiple retrieval steps, or combining narrative disclosures with structured financials. In particular, we need a system that can:

- decide when to query the SQLite database versus the filings
- gather evidence from the right sources
- answer questions that range from direct lookup to multi-step synthesis
- stay grounded in the provided documents and data

We are providing:

- six 10-K filings for Apple, Microsoft, and Alphabet across FY2024 and FY2025
- a local SQLite database with structured financial data
- a 10-question development set

We would like a local proof of concept that a reviewer can run on their machine and interact with directly.

Thanks,  
Natalie Brooks  
Director of Research Systems, Acme Corp

## Project Structure

- `data/`: generated or provided assignment data, including the SQLite DB and 10-K PDFs
- `questions/`: the development-set questions, public dev answer key, and the `dev_answers.json` example template
- `scripts/`: helper scripts that can fetch the SEC source data, render PDFs, and build `financials.db`
- `starter/`: lightweight starter dependencies for setup and experimentation
- `setup.sh`: end-to-end local setup script

## What You Receive

- `questions/dev_questions.json`: 10 development-set questions
- `questions/dev_questions_with_answers.json`: the public dev-set answer key
- `questions/dev_answers_example.json`: template for your `dev_answers.json`
- `setup.sh`: local bootstrap script
- `starter/requirements.txt`: setup and starter dependencies
- `scripts/`: scripts that can fetch or rebuild the data if it is not already present

If `data/financials.db` and the 10-K PDFs are already present, `setup.sh` will reuse them. It only fetches SEC data if it needs to rebuild missing assets.

The dev-set answer key is public so you can evaluate your system locally. We intentionally do not provide an evaluation harness; part of the assignment is deciding how to measure correctness against the provided questions, answers, and data. Fireworks keeps a separate held-out set for the hidden final evaluation.

## Data Overview

The SQLite database includes these tables:

- `companies`: company metadata
- `income_statements`: revenue, gross profit, operating income, net income, EPS, and R&D
- `balance_sheets`: assets, liabilities, equity, cash, debt, and current balance metrics
- `segment_revenue`: revenue by business segment
- `geographic_revenue`: revenue by geography

The filings provide the narrative context needed for questions about risks, strategy, segment definitions, geographic commentary, and management discussion.

## Your Task

Build a local agentic RAG system that can answer increasingly complex questions about the provided companies and filings.

Your system should:

- run locally on a reviewer's machine
- support interactive use (e.g., with a simple UI)
- expose an HTTP API at `http://localhost:8000/api/chat` that accepts `POST` requests with `{"question": "..."}` and returns the answer either as JSON with a top-level `answer` or `content` field (for example, `{"answer": "..."}`) or as an SSE stream with an `answer` event whose data is `{"content": "..."}`.
- route questions to the right source or sources
- return grounded answers that make it easy to inspect evidence
- handle both straightforward retrieval and multi-step reasoning

## Submission Guidelines

- Submit within the deadline provided by your recruiter.
- You may use any Fireworks model and additional framework, database, or vector store.
- You may use the internet, documentation, third-party packages, and AI coding tools.
- If you use AI assistance, mention how in your report.
- Keep external API usage to a reasonable prototype budget.

## Required Deliverables

- A zip file containing your implementation.
- A `README` in your submission with exact local run instructions, required environment variables, and any setup steps.
- A local interactive entry point so a reviewer can ask ad hoc questions.
- A `dev_answers.json` file with your answers to the 10 development questions.
- A short report, about 1 to 2 pages, covering:
  - what you built
  - how the system is structured
  - how you retrieve from SQL and PDFs
  - how you evaluate the system
  - what trade-offs you made and why
  - what you would improve with more time

## `dev_answers.json` Format

Create `dev_answers.json` by copying `questions/dev_answers_example.json`, then fill in your answers as a JSON object keyed by question ID:

```json
{
  "q_001": "<your answer>",
  "q_006": "<your answer>",
  "q_008": "<your answer>"
}
```

Answers may be short or long depending on the question. For synthesis questions, concise but well-supported answers are preferred.

Because the dev answer key is public, `dev_answers.json` is not the hidden evaluation target. We still ask you to submit it so we can see the exact outputs your final system produced on the public development set.

## Getting Started

Run:

```bash
./setup.sh
```

What `setup.sh` does:

- creates a local virtual environment with `uv`
- installs setup and starter dependencies
- downloads the SEC companyfacts JSON if needed
- renders the six 10-K PDFs if needed
- builds `data/financials.db` if needed

Then inspect:

- `data/financials.db`
- `data/pdfs/`
- `questions/dev_questions.json`
- `questions/dev_questions_with_answers.json`

You should use the public answer key to design your own evaluation approach for the dev set.

## How We Will Review

We will review your submission using:

- the quality of the local interactive system
- your ability to route between SQL and PDF-based evidence
- how thoughtfully you evaluate your system against the public dev set
- the clarity of your report and trade-off discussion
- an internal held-out evaluation set

## AI Assistance Disclosure
As permitted by the assignment guidelines, I utilized an AI coding assistant (Agentic AI) to help automate rote boilerplate generation for the FastAPI backend structure, scaffold dynamic vanilla CSS/HTML blocks for the frontend UI, and rapidly generate syntax for logging utilities during the evaluation loop iteration phase. All core logic, system architecture, API orchestration prompts, data handling, and evaluation trade-offs were manually steered and validated. This is also formally logged in `REPORT.md`.
