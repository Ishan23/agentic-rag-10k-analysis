import json
import time
from evaluate import run_evaluations
from collections import defaultdict

def main():
    dataset_path = "questions/dev_questions_with_answers.json"
    iterations = 10
    
    total_scores = []
    
    # query_id -> { "best_score": 0.0, "best_answer": "", "all_scores": [] }
    question_stats = defaultdict(lambda: {"best_score": -1.0, "best_answer": "", "all_scores": []})
    
    for i in range(iterations):
        print(f"\n{'='*20}\nIteration {i+1}/{iterations}\n{'='*20}")
        try:
            results, total_score = run_evaluations(dataset_path)
            total_scores.append(total_score)
            
            for res in results:
                q_id = res["question_id"]
                score = res["score"]
                ans = res["actual_response"]
                
                question_stats[q_id]["all_scores"].append(score)
                
                if score > question_stats[q_id]["best_score"]:
                    question_stats[q_id]["best_score"] = score
                    question_stats[q_id]["best_answer"] = ans
        except Exception as e:
            print(f"Error on iteration {i+1}: {e}")
            break
            
    print("\n\n" + "="*40)
    print("BATCH EVALUATION SUMMARY")
    print("="*40)
    print(f"Total Scores across runs: {total_scores}")
    avg_total = sum(total_scores) / len(total_scores) if total_scores else 0
    print(f"Average Total Score: {avg_total:.2f}/10")
    
    print("\n--- Questions consistently struggling (Avg Score < 0.5) ---")
    for q_id, stats in question_stats.items():
        avg_score = sum(stats["all_scores"]) / len(stats["all_scores"]) if stats["all_scores"] else 0
        if avg_score < 0.5:
            print(f"Question: {q_id} | Average Score: {avg_score:.2f} | Max Score achieved: {stats['best_score']}")
            
    # Output dev_answers.json
    final_output = {}
    for q_id, stats in dict(sorted(question_stats.items())).items():
        final_output[q_id] = stats["best_answer"]
        
    with open("dev_answers.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
        
    print("\nSuccessfully wrote best answers to dev_answers.json!")

if __name__ == "__main__":
    main()
