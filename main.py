import os
import time
import sqlite3
import numpy as np
import pickle
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
import json

load_dotenv()

# --- Initialization ---
env_path = os.path.join(os.getcwd(), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"✅ Found .env at {env_path}")
else:
    print(f"❌ Could not find .env file at {env_path}")

fw_api_key = os.getenv("FIREWORKS_API_KEY")
if not fw_api_key:
    raise ValueError("FIREWORKS_API_KEY not found in environment variables")

app = FastAPI()

# Mount the static directory for the web UI
app.mount("/static", StaticFiles(directory="static"), name="static")

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=fw_api_key,
)

# Load pre-computed embeddings and text chunks at startup
try:
    CHUNK_EMBEDDINGS = np.load('data/embeddings.npy')
    with open('data/chunks.pkl', 'rb') as f:
        CHUNKS = pickle.load(f)
    print(f"🚀 Vector Store Loaded: {len(CHUNKS)} chunks ready.")
except FileNotFoundError:
    print("⚠️ Vector store files not found. Ensure data/embeddings.npy and data/chunks.pkl are present.")

# --- Tools ---
def query_financial_db(sql_query: str):
    """Executes a SQL query against the local financials.db and returns JSON results."""
    conn = sqlite3.connect('data/financials.db')
    try:
        df = pd.read_sql_query(sql_query, conn)
        return df.to_json(orient="records")
    except Exception as e:
        return f"Error: {e}"
    finally:
        conn.close()

def search_10k_filings(query: str):
    """Performs semantic vector search over the processed 10-K filings."""
    # 1. Generate query embedding
    resp = client.embeddings.create(
        input=[query],
        model="nomic-ai/nomic-embed-text-v1.5"
    )
    query_emb = np.array(resp.data[0].embedding)
    
    # 2. Compute cosine similarity against all chunks
    similarities = np.dot(CHUNK_EMBEDDINGS, query_emb) / (
        np.linalg.norm(CHUNK_EMBEDDINGS, axis=1) * np.linalg.norm(query_emb)
    )
    
    # 3. Retrieve and return top 5 matching segments
    top_indices = np.argsort(similarities)[-5:][::-1]
    results = [CHUNKS[i] for i in top_indices]
    
    return "\n---\n".join(results)

def get_system_prompt():
    """Returns the comprehensive system prompt for the financial analyst agent."""
    return """
    You are a financial assistant. You do not have any internal financial data.
    If the user asks for a number, a comparison, or a trend, you MUST call the 'query_financial_db' tool.
    Do not say "I don't have data" until you have attempted to use the tool. Once you have the data from the tools, do not call any more tools. Provide a final, concise answer to the user based on the results.
    
    Use these tables for SQL queries:
    - companies: (ticker, name, cik, sic, sector, fiscal_year_end)
    - income_statements: (id, company_ticker, fiscal_year, period_start, period_end, period_type, revenue, cost_of_revenue, gross_profit, research_and_development, total_operating_expenses, operating_income, net_income, eps_basic, eps_diluted)
    - balance_sheets: (id, company_ticker, fiscal_year, period_end, period_type, total_assets, total_liabilities, stockholders_equity, cash_and_equivalents, total_debt, short_term_debt, accounts_receivable, total_current_assets, total_current_liabilities)
    - segment_revenue: (id, company_ticker, fiscal_year, period_end, period_type, segment_name, revenue)
    - geographic_revenue: (id, company_ticker, fiscal_year, period_end, period_type, region, revenue)

    ENTITY MAPPING RULES:
    - If the user says 'Google', search for 'Alphabet Inc.' or use LIKE '%Alphabet%'.

    CRITICAL SQL RULES:
    1. DATA AVAILABILITY: Most data ends in 2023. If a user asks for 2024 or 2025 and it's null, inform them of the latest available year.
    2. FUZZY SEARCH: Always use 'LIKE' with '%' for company names (e.g., name LIKE '%Apple%').
    3. COMPREHENSIVE SELECT: When comparing or finding the 'highest', always SELECT both the 'name' and the 'value' column (e.g., SELECT name, net_income...).
    4. JOIN: Always JOIN 'companies' with other tables using 'companies.ticker = [table].company_ticker'.
    5. SELF-DOCUMENTING QUERIES: Always SELECT the company name and fiscal_year alongside the metric (e.g., SELECT companies.name, fiscal_year, revenue...). This ensures the data is correctly attributed.
    6. LABELING: Every query should SELECT the company name and fiscal_year. Even for percentages. Example: SELECT companies.name, fiscal_year, (SUM(...) * 1.0 / SUM(...)) * 100 AS percentage ...
    7. DIVISION & PERCENTAGES: To avoid 'Integer Division' errors (getting 0), always cast at least one value to REAL or multiply by 1.0 before dividing. Example: (SUM(revenue) * 1.0 / total_revenue) * 100
    8. MANDATORY PREFIXING: To avoid 'ambiguous column' errors, EVERY SINGLE COLUMN in the SELECT, JOIN, and WHERE clauses MUST be prefixed with its table name (e.g., use 'income_statements.revenue' instead of 'revenue').
    9. GROWTH CALCULATIONS: To find the 'fastest growth between the two most recent years', do not use window functions like LAG on the whole table. Instead, explicitly JOIN the income_statements table to itself (e.g., FROM income_statements AS curr JOIN income_statements AS prev) where curr.fiscal_year = prev.fiscal_year + 1 and filter for the specific most recent year.

    ARCHITECTURAL RULES:
    1. NO OVER-JOINING: Never JOIN 'income_statements' and 'segment_revenue' in the same query. This causes data duplication and limit clipping.
    2. SEQUENTIAL DATA GATHERING: For complex comparisons across companies and years:
       - Step 1: Query 'income_statements' for ALL target companies and years to find the 'Total Revenue' and 'Growth'.
       - Step 2: Based on those results, identify the company with the largest increase.
       - Step 3: Run a second, separate query on 'segment_revenue' for THAT specific company to get the breakdown.
    3. REMOVE LIMITS: Do not use 'LIMIT' when querying for multiple companies or segments unless specifically asked for a 'Top X' list.
    4. TABLE PREFIXES: Always use table names for all columns (e.g., income_statements.revenue) to prevent ambiguity.

    MULTI-STEP REASONING:
    If a question is complex (like comparing growth across companies AND segments):
    1. First, call 'query_financial_db' to get the total revenue for the companies and years needed.
    2. Second, call 'query_financial_db' again to get the segment breakdowns.
    3. Finally, combine the data in your head to provide the answer.
    4. Do not attempt to JOIN 'income_statements' and 'segment_revenue' in a single query.

    REVENUE GROWTH PROTOCOL:
    1. First, query 'SELECT MAX(fiscal_year) FROM income_statements' to identify the actual latest data point.
    2. Once the years are confirmed (e.g., 2023 and 2024), use a SELF-JOIN to calculate the growth:
        SELECT companies.name, ((curr.revenue * 1.0 / prev.revenue) - 1) * 100 AS growth
        FROM income_statements curr
        JOIN income_statements prev ON curr.company_ticker = prev.company_ticker AND curr.fiscal_year = prev.fiscal_year + 1
        WHERE curr.fiscal_year = [LATEST_YEAR]
        ORDER BY growth DESC LIMIT 1;

    Example: "Apple's 2023 revenue"
    SELECT revenue FROM income_statements JOIN companies ON companies.ticker = income_statements.company_ticker WHERE companies.name = 'Apple' AND fiscal_year = 2023;

    Once you have gathered all necessary information from the tools, provide 
    a professional, natural language summary as a financial analyst. 
    Do not return raw JSON to the user.
    """

# --- Agent Logic ---
async def run_agentic_loop(user_message: str):
    """Main execution loop for the agent, handling tool coordination and final synthesis."""
    start_time = time.time()
    sql_queries = []
    total_tokens = 0
    
    # Define available tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_financial_db",
                "description": "Get hard numbers (revenue, net income) from the SQL database.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql_query": {"type": "string"}},
                    "required": ["sql_query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_10k_filings",
                "description": "REQUIRED: You must call this function to answer any qualitative questions. Do not write JSON yourself; use the tool-call feature.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string", 
                            "description": "A specific search query for the 10-K document."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # Initialize conversation state
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": user_message}
    ]

    max_turns = 5
    for turn in range(max_turns):
        # 1. Get model completion
        response = client.chat.completions.create(
            model="accounts/fireworks/models/llama-v3p3-70b-instruct",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        content = response_message.content
        tool_calls = response_message.tool_calls
        
        messages.append(response_message)
        total_tokens += getattr(response.usage, "total_tokens", 0)

        # 2. Handle tool calls (Native support)
        if tool_calls:
            for tool_call in tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = ""
                if tool_call.function.name == "query_financial_db":
                    sql_queries.append(args['sql_query'])
                    result = f"SQL Result: {query_financial_db(args['sql_query'])}"
                elif tool_call.function.name == "search_10k_filings":
                    result = f"10K Result: {search_10k_filings(args['query'])}"
      
                # Inject tool results into history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result
                })
            continue
        
        # 3. Handle Fallback (Manual JSON parsing for hallucinated calls)
        elif content and ("{" in content):
            try:
                # Clean content and isolate potential JSON block
                clean_content = content.replace("```json", "").replace("```", "").replace("<|python_tag|>", "").strip()
                start_idx = clean_content.find('{')
                end_idx = clean_content.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    clean_content = clean_content[start_idx:end_idx]
                
                call_data = json.loads(clean_content)
                if isinstance(call_data, list) and len(call_data) > 0:
                    call_data = call_data[0]
                
                name = call_data.get("name")
                args = call_data.get("parameters", call_data) 
                
                result = ""
                if name == "query_financial_db":
                    sql = args.get('sql_query')
                    if sql:
                        sql_queries.append(sql)
                        result = f"SQL Query Executed: {sql}\nSQL_DATA: {query_financial_db(sql)}"
                elif name == "search_10k_filings":
                    q = args.get('query')
                    if q:
                        search_result = search_10k_filings(q)
                        result = f"10-K Search Query: {q}\nRetrieved Text: {search_result}"
                
                if result:
                    messages.append({
                        "role": "user", 
                        "content": f"SYSTEM NOTIFICATION: Tool '{name}' executed. Results: {result}"
                    })
                    continue
            except Exception as e:
                pass

        # 4. Return final response with collected telemetry
        metrics = {
            "sql_queries": sql_queries,
            "turn_count": turn + 1,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "total_tokens": total_tokens
        }
        return content, metrics
    
    # Return completion status if max turns reached
    metrics = {
        "sql_queries": sql_queries,
        "turn_count": max_turns,
        "latency_ms": round((time.time() - start_time) * 1000, 2),
        "total_tokens": total_tokens
    }
    return "Max turns reached without a final answer.", metrics

# --- API Endpoints ---
@app.get("/")
async def root():
    """Serves the main application entry point."""
    return FileResponse("static/index.html")

class ChatRequest(BaseModel):
    question: str

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Processes analyst questions and returns grounded and metrics."""
    if not request.question:
        raise HTTPException(status_code=400, detail="Question is required")
    
    response_text, metrics = await run_agentic_loop(request.question)
    return {"answer": response_text, "metrics": metrics}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)