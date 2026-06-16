"""
Bonus framework comparison for the Day 14 evaluation lab.

This script completes the optional bonus requirement: run two evaluation
approaches on the same dataset and compare their scores.

Run:
    python bonus_framework_comparison.py

Framework A:
    RAGAS-inspired deterministic overlap metrics from solution/solution.py.

Framework B:
    LLM-as-Judge rubric evaluation with 1-5 scoring, normalized to 0-1 by
    LLMJudge.score_response().

The judge function in this file is deterministic, so the result is repeatable
and does not require API keys. In production, it can be replaced with a real
judge model call or a DeepEval-based evaluator.
"""

from __future__ import annotations

import json
from pathlib import Path

from solution.solution import BenchmarkRunner, LLMJudge, QAPair, RAGASEvaluator, _tokenize


# Completion note:
# Use the same QA set for both evaluators so the framework comparison is fair.
QA_PAIRS = [
    QAPair(
        "What is RAG?",
        "RAG stands for Retrieval-Augmented Generation and combines retrieval with text generation.",
        "RAG stands for Retrieval-Augmented Generation and combines retrieval with text generation grounded in documents.",
    ),
    QAPair(
        "What does faithfulness measure?",
        "Faithfulness measures whether an answer is grounded in the provided context.",
        "Faithfulness measures whether an answer is grounded in provided context and avoids unsupported claims.",
    ),
    QAPair(
        "What is context recall?",
        "Context recall measures how much required evidence from the expected answer appears in retrieved chunks.",
        "Context recall measures how much required evidence from the expected answer appears in retrieved chunks.",
    ),
    QAPair(
        "What is MRR in retrieval evaluation?",
        "MRR is the mean reciprocal rank of the first relevant retrieved document.",
        "MRR is the mean reciprocal rank of the first relevant retrieved document in retrieval evaluation.",
    ),
    QAPair(
        "What is a golden dataset?",
        "A golden dataset is a reviewed set of question answer pairs with expected answers and metadata.",
        "A golden dataset is a reviewed set of question answer pairs with expected answers, metadata, and source documents.",
    ),
    QAPair(
        "Why evaluate retrieval before generation in RAG?",
        "Evaluate retrieval first because missed evidence creates a ceiling that generation cannot fix.",
        "Retrieval should be evaluated before generation because missed evidence creates a ceiling that generation cannot fix.",
    ),
    QAPair(
        "How do context recall and context precision differ?",
        "Context recall checks whether enough evidence was retrieved; context precision checks whether relevant chunks are ranked high.",
        "Context recall checks whether enough evidence was retrieved, while context precision checks whether relevant chunks are ranked high.",
    ),
    QAPair(
        "Why use multi-judge consensus for LLM-as-Judge?",
        "Multi-judge consensus reduces single judge bias and reports agreement before resolving conflicts.",
        "Multi-judge consensus reduces single judge bias, reports agreement rate, and resolves conflicts with a tie breaker.",
    ),
    QAPair(
        "When should an eval gate run in CI/CD?",
        "An eval gate should run before merge or deploy, and after prompt or agent changes.",
        "An eval gate should run before merge or deploy after prompt or agent changes to block regressions.",
    ),
    QAPair(
        "How do 5 Whys help failure analysis?",
        "5 Whys repeatedly asks why a failure happened until the root cause stage is identified.",
        "5 Whys asks why a failure happened until the root cause stage such as retrieval or prompting is identified.",
    ),
]


def mock_agent(question: str) -> str:
    """Return deterministic mock answers so the comparison is reproducible."""
    lookup = {
        "rag": "RAG stands for Retrieval-Augmented Generation and combines retrieval with generation.",
        "faithfulness": "Faithfulness measures whether an answer is grounded in the provided context.",
        "context recall": "Context recall checks whether enough required evidence appears in retrieved chunks.",
        "mrr": "MRR is the mean reciprocal rank of the first relevant retrieved document.",
        "golden dataset": "A golden dataset is a reviewed set of question answer pairs with expected answers and metadata.",
        "retrieval before generation": "Retrieval should be evaluated first because missed evidence creates a ceiling that generation cannot fix.",
        "context precision": "Context recall checks evidence coverage; context precision checks whether relevant chunks are ranked high.",
        "multi-judge": "Multi-judge consensus reduces single judge bias and records agreement before resolving conflicts.",
        "eval gate": "An eval gate should run before merge or deploy after prompt, model, or retriever changes.",
        "5 whys": "5 Whys repeatedly asks why a failure happened until the root cause stage is identified.",
    }
    lower = question.lower()

    # Sort by phrase length so specific keys such as "context precision" are
    # checked before shorter overlapping keys such as "rag".
    for key, answer in sorted(lookup.items(), key=lambda item: len(item[0]), reverse=True):
        if key in lower:
            return answer
    return "I do not know from the provided context."


def deterministic_judge_llm(prompt: str) -> str:
    """Mock a judge LLM by returning rubric scores on the required 1-5 scale."""
    try:
        question = prompt.split("Question:\n", 1)[1].split("\n\nAnswer:\n", 1)[0]
        answer = prompt.split("\n\nAnswer:\n", 1)[1].split("\n\nRubric:\n", 1)[0]
    except IndexError:
        question = ""
        answer = ""

    answer_tokens = _tokenize(answer)
    question_tokens = _tokenize(question)
    relevance = len(answer_tokens & question_tokens) / len(question_tokens) if question_tokens else 1.0

    # Completion note:
    # Return 1-5 scores to match the README rubric requirement. LLMJudge will
    # normalize them to 0-1, which makes the output comparable with other metrics.
    scores_1_to_5 = {
        "correctness": 5 if len(answer_tokens) >= 5 else 3,
        "clarity": 5 if 8 <= len(answer_tokens) <= 28 else 4,
        "relevance": 5 if relevance >= 0.4 else 3 if relevance >= 0.2 else 2,
        "groundedness": 4,
    }
    return json.dumps(scores_1_to_5)


def run_ragas_inspired() -> dict[str, float]:
    """Run Framework A: deterministic RAGAS-inspired metrics."""
    evaluator = RAGASEvaluator()
    runner = BenchmarkRunner()
    results = runner.run(QA_PAIRS, mock_agent, evaluator)
    report = runner.generate_report(results)
    return {
        "pass_rate": round(report["pass_rate"], 3),
        "avg_faithfulness": round(report["avg_faithfulness"], 3),
        "avg_relevance": round(report["avg_relevance"], 3),
        "avg_completeness": round(report["avg_completeness"], 3),
        "avg_overall": round(report["avg_overall"], 3),
    }


def run_llm_judge_rubric() -> dict[str, float]:
    """Run Framework B: LLM-as-Judge rubric scoring on the same QA set."""
    judge = LLMJudge(deterministic_judge_llm)
    rubric = {
        "correctness": "Is the answer factually correct?",
        "clarity": "Is the answer concise and clear?",
        "relevance": "Does the answer address the question?",
        "groundedness": "Is the answer grounded and not overclaiming?",
    }

    per_item_scores = []
    for qa in QA_PAIRS:
        judged = judge.score_response(qa.question, mock_agent(qa.question), rubric)
        per_item_scores.append(sum(judged["scores"].values()) / len(rubric))

    return {
        "pass_rate": round(sum(score >= 0.65 for score in per_item_scores) / len(per_item_scores), 3),
        "avg_rubric_score": round(sum(per_item_scores) / len(per_item_scores), 3),
        "min_rubric_score": round(min(per_item_scores), 3),
        "max_rubric_score": round(max(per_item_scores), 3),
    }


def main() -> None:
    """Run both evaluators and write a JSON comparison report."""
    comparison = {
        "framework_1": {
            "name": "RAGAS-inspired heuristic evaluator",
            "results": run_ragas_inspired(),
        },
        "framework_2": {
            "name": "LLM-as-Judge rubric evaluator, 1-5 scoring normalized to 0-1",
            "results": run_llm_judge_rubric(),
        },
    }

    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    output_path = reports_dir / "framework_comparison.json"
    output_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
