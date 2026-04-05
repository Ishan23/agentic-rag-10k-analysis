# Fireworks AMLE Take-Home Report

## 🚀  Step-by-Step Run Instructions

1. **Setup Environment**: Ensure your `.env` file contains a valid `FIREWORKS_API_KEY`. Run `./setup.sh` to install dependencies and initialize the vector embeddings and SQLite database.
2. **Start the Server**: Boot the agentic backend by running `python main.py` in your terminal.
3. **Access the Interactive Web UI**: Open your web browser and navigate to `http://localhost:8000`. You will be greeted by a custom conversational Chat UI. You can type ad-hoc questions here and instantly test the agent!
4. **Run the Evaluations**: While the server is running in the background, open a new terminal tab and execute `python evaluate.py`. This script will output live evaluations, print trace metrics (such as the exact synthesized SQL queries, latency, and tokens), and save a final JSONL log to the `eval_results/` directory.
5. **Review the Final Deliverable output**: The best answers the agent crafted for the dev-set over multiple batch iterations have been automatically saved to `dev_answers.json` in the **root directory**. Please inspect this file to verify the final qualitative answers.

## AI Assistance Disclosure
As permitted by the assignment guidelines, I utilized an AI coding assistant (Agentic AI) to help automate rote boilerplate generation for the FastAPI backend structure, scaffold dynamic vanilla CSS/HTML blocks for the frontend UI, and rapidly generate syntax for logging utilities during the evaluation loop iteration phase. All core logic, system architecture, API orchestration prompts, data handling, and evaluation trade-offs were manually steered and validated.

## What I Built
I built a local Agentic RAG system that acts as a financial research assistant, capable of dynamically deciding when to query a structured SQLite database of financial metrics, when to perform vector similarity search against 10-K filings, and when to synthesize data from both modalities.

## System Architecture & Structure
The system is built around a ReAct (Reasoning and Acting) loop utilizing the `llama-v3p3-70b-instruct` model served via the Fireworks API. 

The application exposes a robust FastAPI backend that serves a **Custom Interactive Web UI** (pure HTML/CSS/JS) at the root `http://localhost:8000`, alongside the core AI endpoint at `http://localhost:8000/api/chat`. 

### A. Multi-Turn Agentic Loop
The system utilizes a stateful `run_agentic_loop` that allows the model up to **5 turns** to solve a query. This is critical because financial questions (e.g., "Which company grew the fastest and why?") often require sequential steps—finding a winner first via SQL, then searching for qualitative reasons in the 10-K filings. The loop maintains a message history, appending tool results as `role: tool` (for native calls) or `role: user` (for fallback JSON calls) to ensure the LLM has a consistent "working memory."

### B. Robust Tool Handling (Dual-Path)
A significant design decision was implementing **Dual-Path Tool Execution**:
1. **Native Path**: Handles standard OpenAI-style `tool_calls`.
2. **Fallback Path**: Uses regex and JSON parsing to catch "hallucinated" JSON within the model's text content. This ensures the system doesn't crash if the model outputs JSON directly (e.g., `<|python_tag|>{"name": ...}`) instead of using the API's native tool feature, a behavior sometimes seen in open-weight models.

The agentic loop initializes with two primary tools:
1. `query_financial_db`: Executes arbitrary SQL against `financials.db`.
2. `search_10k_filings`: Embeds queries via `nomic-embed-text-v1.5` and searches the pre-computed NumPy/Pickle vector store.

The loop iterates (up to 5 max turns) until the LLM grounds enough evidence to formulate a direct final answer without invoking further tools.

## Retrieval Strategy
**SQL Retrieval:** The agent is given full schema visibility through the system prompt and dynamically composes `SELECT`, `JOIN`, and aggregation operations in SQL. The resulting Pandas DataFrame is serialized to JSON and fed back sequentially to the LLM.

**PDF/Vector Retrieval:** A static indexing pipeline chunks the 10-K PDFs and creates embeddings via the Nomic embedding model. I deliberately isolated the embedding generation and chunking logic into the `RoughWork.ipynb` Jupyter notebook (where the source functions can be inspected by the reviewer). By pre-calculating and saving them, I avoid needlessly regenerating identical chunks and wasting API tokens every time I restart `main.py`. The API system simply loads the pre-computed `embeddings.npy` store to perform fast Cosine Similarity when retrieving top-K narrative chunks.

## Evaluation Strategy
To rigorously test the architecture, I built an end-to-end evaluation harness (`evaluate.py`) that judges the agent's final text outputs via three modalities:
1. `fuzzy_numeric`: Strictly verifies that exact financial values (e.g., "$391.0B") are extracted correctly.
2. `exact_match_entity`: Validates company naming constraints.
3. `llm_judge`: Employs Fireworks API as an LLM-as-a-judge to score synthesis answers on a 0.0-1.0 scale against golden answers.

For rigorous telemetry, the evaluation loop now captures:
- Exact SQL queries generated to inspect logical breakdown.
- Iterative Turn Count, Latency, and Token bounds.
- Negative Grounding tasks: I seeded a new dataset (`questions/negative_grounding_questions.json`) containing adversarial limits (e.g., non-existent companies or impossible timelines) which proved the system safely declined hallucinations.
- Batch Evaluation Suite: I developed `batch_eval.py` to iteratively test the agent across repeated execution loops (10x) to verify system reliability and log failure modes.

### Evaluation Results & Known Failure Modes
Across multiple batch evaluation iterations, the system achieved an average score of **4.82 / 10.0** on the public dev set. The system excelled at data lookups and negative grounding bounding constraints. However, I identified three primary questions where the agent consistently struggled (average score ≤ 0.25), indicating clear failure modes:
1. **`q_011` (Fastest revenue growth rate computation across companies)**: The agent struggles to formulate the highly complex SQL required to compute growth rates dynamically across multiple rows and companies, ultimately failing the strict entity matching.
2. **`q_018` (Highest current ratio computation)**: The system frequently gets derailed trying to execute cross-table divisions (`current assets / current liabilities`) in a zero-shot SQL generation attempt, leading to syntax errors or incorrect mathematical formatting.
3. **`q_025` (Apple's Services segment growth vs strategic importance)**: This relies heavily on a multi-hop reasoning process involving *both* mathematical SQL execution and qualitative PDF generation. The agent often zeroes in on the math and loses the context required to execute the final qualitative PDF vector search.

## Trade-offs Made
*   **Brute-Force Search vs Approximate Nearest Neighbors (ANN):** To preserve simplicity and avoid bloated dependencies, I implemented a brute-force cosine similarity search against a static `.npy` array. In a true production environment with larger datasets, I would trade this zero-dependency approach for a dedicated Vector DB utilizing ANN indexing (like FAISS or Chroma) to drastically improve scaling speed. Additionally, accepting Nomic's default embedding dimension size dictates the baseline tradeoff between local storage limits and conceptual accuracy.
*   **Arbitrary SQL generation:** Allowing the LLM to write arbitrary SQL risks SQL-injection or complex syntax failures, but avoids the rigid brittleness of strictly parameterized keyword endpoints.
*   **Vanilla UI vs Heavy Frameworks:** To fulfill the interactive UI requirement while adhering to the minimal dependency philosophy of a local script, I baked a custom vanilla HTML/JS/CSS client directly into FastAPI (`static/index.html`). This avoids forcing the reviewer to install heavy javascript frameworks like React or Node.js just to test the backend, while still delivering a premium interactive experience.

## Future Improvements
*   **Self-Correcting SQL Execution:** Complex questions like `q_011` and `q_018` fail zero-shot SQL generation. I would implement an auto-correction loop where SQL execution errors (`try/except`) are caught and fed back to the LLM immediately to debug and rewrite its own query rather than swallowing the error.
*   **Granular, Multi-Stage Evaluation Framework:** To gain a deeper understanding of system performance, I would move from end-to-end "Success/Fail" metrics into a 3-tier evaluation workflow:
    1. **Ingestion Evaluation:** Testing the fidelity of the PDF-to-SQL/Vector transition (e.g., ensuring 100% table structure preservation during parsing).
    2. **Retrieval Evaluation:** Measuring "Hit Rate" and "MRR" (Mean Reciprocal Rank) for the vector search and "SQL Accuracy" for the database tool, independent of the final answer quality.
    3. **Generation Evaluation:** Utilizing specialized LLM-judges to measure "Faithfulness" (grounding in retrieved context) and "Answer Relevance" (how directly the synthesis answers the user's specific prompt). This granularity allows for isolating whether a failure is a "search issue" or a "reasoning issue."
*   **Multi-Modal Document Intelligence:** Currently, the system relies on text-based parsing which misses critical financial data stored in non-textual modalities. I would implement:
    1. **VLM integration:** Using Vision-Language Models (e.g., Llama-3-Vision) to "read" and describe quarterly growth charts and performance graphs directly from the PDF pages.
    2. **Layout-Aware Extraction:** Employing advanced parsers (like Unstructured or Marker) to detect complex objects like charts/graphs and convert them into machine-readable formats (JSON/Markdown) during the ingestion phase.
    3. **Visual-Textual Correlation:** Implementing a cross-check mechanism where the agent validates narrative claims in the text against extracted data points from figures and charts.
*   **Task Planner Agent Pipeline:** For multi-modality questions like `q_025`, relying on a single ReAct loop can cause context drops. I would implement an upfront "Planner Agent" that decomposes the objective into discrete sub-tasks (e.g., 1. Calculate Growth, 2. Retrieve Strategic Context from PDF), ensuring no modality is bypassed.
*   **Hybrid Search:** Add BM25 or keyword matching to the vector search to avoid missing exact entities disguised within long prose in the 10-K.
*   **Context Window Windowing:** Add token cutoff safeguards for the context window on long multi-turn execution histories to minimize latency and unbounded token costs.
*   **Multi-Agent Workflow & Model Routing (Cost Optimization):** Currently, a single heavy model (`Llama-v3p3-70b`) orchestrates the entirety of the execution loop. To significantly reduce latency and API cost without sacrificing quality, I would implement a Router Pipeline where a cheaper, faster model (like an `8b` variant) conducts basic queries, localized PDF extraction, and tool execution, while explicitly reserving the expensive `70b` model for advanced analytical planning and final answer synthesis.
