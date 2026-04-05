import os
import json
from datetime import datetime
import requests
import re
import math
from typing import List, Tuple, Any
from openai import OpenAI
from dotenv import load_dotenv

# --- Configuration & Client Setup ---
API_URL = "http://localhost:8000/api/chat"

load_dotenv('.env')
fw_client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv("FIREWORKS_API_KEY"),
)

def get_answer_from_api(question: str) -> str:
    """Sends a POST request to the local FastAPI agent to retrieve the model response."""
    try:
        response = requests.post(API_URL, json={"question": question}, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if "content" in data:
            return data["content"], data.get("metrics", {})
        elif "answer" in data:
            return data["answer"], data.get("metrics", {})
        else:
            return f"Error: No valid key found in response: {data}", {}
    except Exception as e:
        return f"API Error: {str(e)}", {}

# =====================================================================
# LLM Evaluator Logic
# =====================================================================

def call_llm_for_eval(prompt: str) -> str:
    """Helper method to prompt the LLaMA model for automated grading results."""
    try:
        response = fw_client.chat.completions.create(
            model="accounts/fireworks/models/llama-v3p3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling LLM evaluator: {e}")
        return "MATCH: 0.0\nVALUE: 0\nSCORE: 0.0"

# =====================================================================
# Evaluator functions
# =====================================================================

def evaluate_exact_match_entity(actual_response: str, gold_answer: str, gold_numeric: float = None) -> float:
    """Grades whether the primary entity and optional numeric value are present in the response."""
    numeric_instruction = ""
    if gold_numeric is not None:
        numeric_instruction = f"\nAdditionally, verify that the Actual Answer contains the exact numerical value: {gold_numeric}."

    prompt = f"""You are an entity extraction and matching assistant.
You are given a Ground Truth Answer containing a key entity (such as a numeric value or company name) and an Actual Answer.
Your task is to determine if the exact key entity or entities from the Ground Truth Answer are present in the Actual Answer.
Focus on proper nouns representing the primary subject (e.g., "Alphabet", "Apple", "Microsoft").{numeric_instruction}

If all required criteria are identified, output 1.0. Otherwise, output 0.0.

Ground Truth Answer: {gold_answer}
Actual Answer: {actual_response}

Final Score (exact format: MATCH: 1.0 or MATCH: 0.0):"""

    llm_output = call_llm_for_eval(prompt)
    match = re.search(r"MATCH:\s*(1\.0|0\.0|1|0)", llm_output)
    if not match:
        return 1.0 if "1.0" in llm_output else 0.0
        
    try:
        return float(match.group(1))
    except ValueError:
        return 0.0

def evaluate_fuzzy_numeric(actual_response: str, gold_numeric: float) -> float:
    """Extracts numeric values and verifies them against a 5% tolerance threshold."""
    if gold_numeric is None:
        return 0.0
        
    prompt = f"""Extract the primary numerical answer from the Provided Text.
Convert textual scales (e.g. billion -> 10^9).
Provided Text: {actual_response}

Final Number (exact format: VALUE: <number>):"""

    llm_output = call_llm_for_eval(prompt)
    match = re.search(r"VALUE:\s*(-?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", llm_output)
    if not match:
        match = re.search(r"(-?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)", llm_output)
        
    if match:
        try:
            extracted_num = float(match.group(1))
            if extracted_num == 0 and gold_numeric == 0:
                return 1.0
            elif gold_numeric != 0:
                # Calculate relative difference for 5% tolerance
                if abs(extracted_num - gold_numeric) / abs(gold_numeric) <= 0.05:
                    return 1.0
        except ValueError:
            pass
            
    return 0.0

def evaluate_llm_judge(question: str, actual_response: str, gold_answer: str) -> float:
    """Performs a qualitative fact-matching comparison using a rubric-based score (0.0 to 1.0)."""
    prompt = f"""You are an expert evaluator for a financial assistant.
Score the Actual Answer on a scale of 0.0 to 1.0 against the Ground Truth Answer.

- 1.0: Perfectly matches information and intent.
- 0.5: Partially covers information or misses nuance.
- 0.0: Incorrect or fails to accurately answer.

Question: {question}
Ground Truth: {gold_answer}
Actual Answer: {actual_response}

Think step by step and output: SCORE: <number between 0.0 and 1.0>"""
    
    llm_output = call_llm_for_eval(prompt)
    match = re.search(r"SCORE:\s*([0-9]*\.?[0-9]+)", llm_output)
    if match:
        try:
            return max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            return 0.0
    return 0.0

# =====================================================================
# Execution Flow
# =====================================================================

def run_evaluations(dataset_path: str):
    """Main driver for the evaluation sequence across the provided dataset."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
        
    print(f"Loaded {len(questions)} questions for evaluation from {dataset_path}\n")
    results = []
    
    for item in questions:
        q_id, q_text = item.get("id"), item.get("question")
        gold_answer, gold_numeric = item.get("gold_answer"), item.get("gold_answer_numeric")
        eval_type = item.get("evaluation")
        
        print(f"Evaluating {q_id}: {q_text}")
        actual_response, metrics = get_answer_from_api(q_text)
        
        score = 0.0
        if eval_type == "exact_match_entity":
            score = evaluate_exact_match_entity(actual_response, gold_answer, gold_numeric)
        elif eval_type == "fuzzy_numeric":
            score = evaluate_fuzzy_numeric(actual_response, gold_numeric)
        elif eval_type == "llm_judge":
            score = evaluate_llm_judge(q_text, actual_response, gold_answer)
            
        print(f"  Result: {score} | {metrics.get('turn_count')} turns | {metrics.get('latency_ms')}ms")
        print("-" * 50)
        
        results.append({
            "question_id": q_id,
            "golden_response": gold_answer,
            "actual_response": actual_response,
            "evaluation_type": eval_type,
            "score": score,
            "metrics": metrics
        })
        
    # Summarize final metrics and averages
    total_score = sum(r["score"] for r in results)
    print(f"\n================ EVALUATION SUMMARY ================")
    print(f"Total Score: {total_score} / {len(results)}")
    
    valid_metrics = [r["metrics"] for r in results if r.get("metrics")]
    if valid_metrics:
        avg_turn = sum(m.get("turn_count", 0) for m in valid_metrics) / len(valid_metrics)
        avg_lat = sum(m.get("latency_ms", 0) for m in valid_metrics) / len(valid_metrics)
        avg_tok = sum(m.get("total_tokens", 0) for m in valid_metrics) / len(valid_metrics)
        print(f"\n--- Performance Summary ---")
        print(f"Average Turn Count : {avg_turn:.2f}")
        print(f"Average Latency    : {avg_lat:.2f} ms")
        print(f"Average Tokens/Req : {avg_tok:.0f} tokens\n")
    
    # Export results to timestamped JSONL
    os.makedirs("eval_results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = os.path.join("eval_results", f"eval_results_{timestamp}.jsonl")
    
    with open(out_filename, "w", encoding="utf-8") as out_f:
        for r in results: out_f.write(json.dumps(r) + "\n")
            
    print(f"Evaluation results saved to {out_filename}")
    return results, total_score
    
if __name__ == "__main__":
    run_evaluations("questions/dev_questions_with_answers.json")
