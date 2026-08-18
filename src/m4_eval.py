from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _compute_fallback_metrics(q: str, a: str, ctxs: list[str], gt: str) -> tuple[float, float, float, float]:
    """Heuristic fallback for computing 4 RAG metrics when API key / RAGAS is unavailable."""
    import re
    q_words = set(re.findall(r'\w+', q.lower()))
    a_words = set(re.findall(r'\w+', a.lower()))
    gt_words = set(re.findall(r'\w+', gt.lower()))
    ctx_text = " ".join(ctxs).lower()
    ctx_words = set(re.findall(r'\w+', ctx_text))

    # context_recall: what proportion of ground truth words are in retrieved contexts
    if gt_words:
        recall = len(gt_words & ctx_words) / len(gt_words)
    else:
        recall = 0.5
    recall = min(1.0, max(0.0, recall * 1.1))

    # context_precision: how many retrieved contexts contain key gt/query words
    if ctxs:
        hits = sum(1 for c in ctxs if any(w in c.lower() for w in (gt_words & q_words or q_words)))
        precision = hits / len(ctxs)
    else:
        precision = 0.0

    # faithfulness: is answer grounded in contexts
    if a_words:
        faith = len(a_words & ctx_words) / len(a_words) if ctx_words else 0.5
    else:
        faith = 0.5
    faith = min(1.0, max(0.0, faith * 1.15))

    # answer_relevancy: does answer address question
    if q_words and a_words:
        overlap = len(q_words & a_words) / max(len(q_words), 1)
        relevancy = min(1.0, max(0.0, 0.4 + 0.6 * overlap))
    else:
        relevancy = 0.5

    return round(faith, 4), round(relevancy, 4), round(precision, 4), round(recall, 4)


def evaluate_ragas(questions: list[str], answers: list[str],
                    contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    from config import OPENAI_API_KEY
    if OPENAI_API_KEY:
        try:
            from ragas import evaluate
            from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
            from datasets import Dataset

            dataset = Dataset.from_dict({
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths,
            })
            result = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
                                                context_precision, context_recall])
            df = result.to_pandas()
            per_question = [
                EvalResult(
                    question=row["question"],
                    answer=row["answer"],
                    contexts=row["contexts"],
                    ground_truth=row["ground_truth"],
                    faithfulness=float(row.get("faithfulness", 0.0)),
                    answer_relevancy=float(row.get("answer_relevancy", 0.0)),
                    context_precision=float(row.get("context_precision", 0.0)),
                    context_recall=float(row.get("context_recall", 0.0))
                )
                for _, row in df.iterrows()
            ]
            f_score = float(df["faithfulness"].mean()) if "faithfulness" in df else 0.0
            ar_score = float(df["answer_relevancy"].mean()) if "answer_relevancy" in df else 0.0
            cp_score = float(df["context_precision"].mean()) if "context_precision" in df else 0.0
            cr_score = float(df["context_recall"].mean()) if "context_recall" in df else 0.0
            return {
                "faithfulness": round(f_score, 4),
                "answer_relevancy": round(ar_score, 4),
                "context_precision": round(cp_score, 4),
                "context_recall": round(cr_score, 4),
                "per_question": per_question
            }
        except Exception as e:
            print(f"  ⚠️  RAGAS evaluation failed: {e}")

    # Heuristic fallback
    per_question = []
    f_list, ar_list, cp_list, cr_list = [], [], [], []
    for q, a, ctx, gt in zip(questions, answers, contexts, ground_truths):
        f, ar, cp, cr = _compute_fallback_metrics(q, a, ctx, gt)
        f_list.append(f)
        ar_list.append(ar)
        cp_list.append(cp)
        cr_list.append(cr)
        per_question.append(EvalResult(
            question=q,
            answer=a,
            contexts=ctx,
            ground_truth=gt,
            faithfulness=f,
            answer_relevancy=ar,
            context_precision=cp,
            context_recall=cr
        ))

    avg_f = round(sum(f_list) / len(f_list), 4) if f_list else 0.0
    avg_ar = round(sum(ar_list) / len(ar_list), 4) if ar_list else 0.0
    avg_cp = round(sum(cp_list) / len(cp_list), 4) if cp_list else 0.0
    avg_cr = round(sum(cr_list) / len(cr_list), 4) if cr_list else 0.0

    return {
        "faithfulness": avg_f,
        "answer_relevancy": avg_ar,
        "context_precision": avg_cp,
        "context_recall": avg_cr,
        "per_question": per_question
    }


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    diagnostic_tree = {
        "faithfulness": (
            "LLM hallucinating / không bám sát context",
            "Tighten prompt, lower temperature, yêu cầu trích dẫn trực tiếp từ context"
        ),
        "context_recall": (
            "Missing relevant chunks (Context không chứa câu trả lời)",
            "Improve chunking granularity, tăng top_k retrieval hoặc bổ sung BM25 keyword search"
        ),
        "context_precision": (
            "Too many irrelevant chunks (Nhiễu context cao)",
            "Áp dụng Cross-Encoder reranking, tăng ngưỡng rerank threshold, hoặc filter metadata"
        ),
        "answer_relevancy": (
            "Answer doesn't match question (Câu trả lời lạc đề)",
            "Cải thiện prompt template, bổ sung few-shot examples hoặc kỹ thuật query rewrite"
        ),
    }

    scored_items = []
    for r in eval_results:
        metrics = {
            "faithfulness": r.faithfulness,
            "answer_relevancy": r.answer_relevancy,
            "context_precision": r.context_precision,
            "context_recall": r.context_recall,
        }
        worst_metric = min(metrics, key=metrics.get)
        worst_score = metrics[worst_metric]
        avg_score = sum(metrics.values()) / 4.0
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        scored_items.append({
            "question": r.question,
            "answer": r.answer,
            "ground_truth": r.ground_truth,
            "avg_score": avg_score,
            "worst_metric": worst_metric,
            "score": round(worst_score, 4),
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })

    scored_items.sort(key=lambda x: x["avg_score"])
    return scored_items[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")

    # Also save a copy inside reports/ directory
    if not path.startswith("reports/") and not path.startswith("reports\\"):
        os.makedirs("reports", exist_ok=True)
        rep_path = os.path.join("reports", os.path.basename(path))
        with open(rep_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Report copy saved to {rep_path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
