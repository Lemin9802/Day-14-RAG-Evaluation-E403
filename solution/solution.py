"""
Implementation file for the Day 14 automatic evaluation pipeline.

This file completes the lab TODOs from template.py: data models, RAGAS-inspired
answer/retrieval metrics, LLM-as-Judge scoring, benchmark reporting,
regression checks, and failure-analysis suggestions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable


# Completed Task 1: replace the template placeholder with concrete QAPair fields.
@dataclass
class QAPair:
    """A question-answer pair for a golden evaluation dataset."""

    question: str
    expected_answer: str
    context: str | None = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_contexts: list[str] = field(default_factory=list)


# Completed Task 1: store all evaluation scores and optional retrieval metrics.
@dataclass
class EvalResult:
    """Evaluation result for a single Q&A pair."""

    qa_pair: QAPair
    actual_answer: str
    faithfulness: float
    relevance: float
    completeness: float
    passed: bool
    failure_type: str | None = None
    context_precision: float | None = None
    context_recall: float | None = None

    # Completed Task 1: overall score is the mean of the three answer-side metrics.
    def overall_score(self) -> float:
        """Return the average answer-side score."""
        return (self.faithfulness + self.relevance + self.completeness) / 3.0


# Implementation detail: add common question words to reduce inflated lexical overlap.
STOPWORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "as", "by", "and", "or",
    "it", "its", "this", "that", "these", "those", "from", "into", "than",
    "what", "who", "when", "where", "why", "how", "does", "do", "did",
    "should", "can", "could", "would", "will", "which",
}


# Helper used by all heuristic metrics; accepts None safely for robustness.
def _tokenize(text: str | None) -> set[str]:
    """Lowercase word tokenization, ignoring punctuation and stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b\w+\b", str(text).lower())
    return {token for token in tokens if token not in STOPWORDS}


# Helper to keep all metric outputs inside the required [0, 1] range.
def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _overlap_score(numerator_tokens: set[str], denominator_tokens: set[str]) -> float:
    if not denominator_tokens:
        return 1.0
    return _clamp01(len(numerator_tokens & denominator_tokens) / len(denominator_tokens))


# Completed Task 2 and Task 2b: answer-side and retrieval-side RAGAS-style metrics.
class RAGASEvaluator:
    """RAGAS-inspired evaluator using deterministic word-overlap heuristics."""

    # Completed Task 2: |answer tokens ∩ context tokens| / |answer tokens|.
    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        answer_tokens = _tokenize(answer)
        context_tokens = _tokenize(context)
        return _overlap_score(context_tokens, answer_tokens)

    # Completed Task 2: |answer tokens ∩ question tokens| / |question tokens|.
    def evaluate_relevance(self, answer: str, question: str) -> float:
        answer_tokens = _tokenize(answer)
        question_tokens = _tokenize(question)
        return _overlap_score(answer_tokens, question_tokens)

    # Completed Task 2: |answer tokens ∩ expected tokens| / |expected tokens|.
    def evaluate_completeness(self, answer: str, expected: str) -> float:
        answer_tokens = _tokenize(answer)
        expected_tokens = _tokenize(expected)
        return _overlap_score(answer_tokens, expected_tokens)

    # Completed Task 2b: measure expected-answer coverage over the union of retrieved chunks.
    def evaluate_context_recall(self, contexts: list[str], expected: str) -> float:
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0

        union_tokens: set[str] = set()
        for chunk in contexts or []:
            union_tokens |= _tokenize(chunk)
        return _overlap_score(union_tokens, expected_tokens)

    # Completed Task 2b: rank-aware Average Precision over retrieved chunks.
    def evaluate_context_precision(
        self,
        contexts: list[str],
        expected: str,
        relevance_threshold: float = 0.1,
    ) -> float:
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        if not contexts:
            return 0.0

        relevance_flags: list[bool] = []
        for chunk in contexts:
            chunk_tokens = _tokenize(chunk)
            coverage = len(chunk_tokens & expected_tokens) / len(expected_tokens)
            relevance_flags.append(coverage >= relevance_threshold)

        total_relevant = sum(relevance_flags)
        if total_relevant == 0:
            return 0.0

        running_relevant = 0
        precision_sum = 0.0
        for rank, is_relevant in enumerate(relevance_flags, start=1):
            if is_relevant:
                running_relevant += 1
                precision_sum += running_relevant / rank

        return _clamp01(precision_sum / total_relevant)

    # Completed Task 2: run all metrics, set pass/fail, and classify the failure type.
    def run_full_eval(
        self,
        answer: str,
        question: str,
        context: str,
        expected: str,
        contexts: list[str] | None = None,
    ) -> EvalResult:
        faithfulness = self.evaluate_faithfulness(answer, context)
        relevance = self.evaluate_relevance(answer, question)
        completeness = self.evaluate_completeness(answer, expected)
        passed = faithfulness >= 0.5 and relevance >= 0.5 and completeness >= 0.5

        failure_type: str | None = None
        if not passed:
            if faithfulness < 0.3:
                failure_type = "hallucination"
            elif relevance < 0.3:
                failure_type = "irrelevant"
            elif completeness < 0.3:
                failure_type = "incomplete"
            else:
                failure_type = "off_topic"

        context_recall: float | None = None
        context_precision: float | None = None
        if contexts:
            context_recall = self.evaluate_context_recall(contexts, expected)
            context_precision = self.evaluate_context_precision(contexts, expected)

        return EvalResult(
            qa_pair=QAPair(
                question=question,
                expected_answer=expected,
                context=context,
                retrieved_contexts=list(contexts or []),
            ),
            actual_answer=answer,
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            passed=passed,
            failure_type=failure_type,
            context_precision=context_precision,
            context_recall=context_recall,
        )


# Completed Exercise 3.5: simple lexical reranker to improve rank-aware context precision.
def rerank_by_overlap(contexts: list[str], query: str) -> list[str]:
    """Sort chunks by lexical overlap with a query, descending."""
    query_tokens = _tokenize(query)
    return sorted(
        list(contexts or []),
        key=lambda chunk: len(_tokenize(chunk) & query_tokens),
        reverse=True,
    )


# Completed Task 3: injectable LLM-as-Judge wrapper with JSON score parsing and bias checks.
class LLMJudge:
    """Uses an injected judge function to score responses according to a rubric."""

    def __init__(self, judge_llm_fn: Callable[[str], str]) -> None:
        # Store the injected judge function so tests can use a deterministic mock judge.
        self.judge_llm_fn = judge_llm_fn

    def score_response(
        self,
        question: str,
        answer: str,
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        criteria_lines = "\n".join(f"- {name}: {desc}" for name, desc in rubric.items())
        # README alignment: ask the judge for 1-5 rubric scores, then normalize to 0-1 below.
        prompt = (
            "You are a strict evaluation judge. Score each criterion from 1 to 5.\n"
            "Rubric scale: 5 = excellent, 4 = mostly correct, 3 = partial, "
            "2 = major issues, 1 = wrong/unsupported/irrelevant.\n"
            "Return JSON only, either as {criterion: score_1_to_5} or {'scores': {...}}.\n"
            "The code will normalize 1-5 scores to 0-1 for aggregation.\n\n"
            f"Question:\n{question}\n\n"
            f"Answer:\n{answer}\n\n"
            f"Rubric:\n{criteria_lines}\n"
        )

        raw_response = self.judge_llm_fn(prompt)
        scores: dict[str, float]

        try:
            parsed = json.loads(raw_response)
            score_source = parsed.get("scores", parsed) if isinstance(parsed, dict) else {}
            scores = {}
            for criterion in rubric:
                raw_value = score_source.get(criterion, 0.5) if isinstance(score_source, dict) else 0.5
                try:
                    value = float(raw_value)
                    if 1.0 < value <= 5.0:
                        value = value / 5.0
                    scores[criterion] = _clamp01(value)
                except (TypeError, ValueError):
                    scores[criterion] = 0.5
        except (json.JSONDecodeError, TypeError):
            scores = {criterion: 0.5 for criterion in rubric}

        return {"scores": scores, "reasoning": raw_response}

    # Completed Task 3: detect positional, leniency, and severity bias from score batches.
    def detect_bias(self, scores_batch: list[dict[str, Any]]) -> dict[str, Any]:
        flat_scores: list[float] = []
        first_position_scores: list[float] = []
        other_position_scores: list[float] = []

        for item in scores_batch or []:
            scores = item.get("scores", {}) if isinstance(item, dict) else {}
            numeric_scores = [float(v) for v in scores.values() if isinstance(v, (int, float))]
            if not numeric_scores:
                continue

            avg_score = sum(numeric_scores) / len(numeric_scores)
            flat_scores.append(avg_score)

            position = item.get("position", item.get("answer_position", item.get("response_position")))
            is_first = item.get("is_first")
            if position in (0, 1, "first", "A") or is_first is True:
                first_position_scores.append(avg_score)
            elif position is not None or is_first is False:
                other_position_scores.append(avg_score)

        avg = sum(flat_scores) / len(flat_scores) if flat_scores else 0.0
        positional_bias = False
        if first_position_scores and other_position_scores:
            first_avg = sum(first_position_scores) / len(first_position_scores)
            other_avg = sum(other_position_scores) / len(other_position_scores)
            positional_bias = first_avg - other_avg > 0.10

        return {
            "positional_bias": positional_bias,
            "leniency_bias": avg > 0.8,
            "severity_bias": bool(flat_scores) and avg < 0.3,
        }


# Completed Task 4: run benchmarks, summarize aggregate metrics, and detect regressions.
class BenchmarkRunner:
    """Runs a full evaluation benchmark."""

    # Completed Task 4: call the agent for each QAPair and evaluate each answer.
    def run(
        self,
        qa_pairs: list[QAPair],
        agent_fn: Callable[[str], str],
        evaluator: RAGASEvaluator,
    ) -> list[EvalResult]:
        results: list[EvalResult] = []
        for pair in qa_pairs:
            answer = agent_fn(pair.question)
            contexts = pair.retrieved_contexts or None
            result = evaluator.run_full_eval(
                answer=answer,
                question=pair.question,
                context=pair.context or "",
                expected=pair.expected_answer,
                contexts=contexts,
            )
            result.qa_pair = pair
            results.append(result)
        return results

    # Completed Task 4: aggregate pass rate, average scores, and failure distribution.
    def generate_report(self, results: list[EvalResult]) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "passed": 0,
                "pass_rate": 0.0,
                "avg_faithfulness": 0.0,
                "avg_relevance": 0.0,
                "avg_completeness": 0.0,
                "avg_overall": 0.0,
                "failure_types": {},
            }

        passed_count = sum(1 for result in results if result.passed)
        failure_types: dict[str, int] = {}
        for result in results:
            if not result.passed:
                key = result.failure_type or "unknown"
                failure_types[key] = failure_types.get(key, 0) + 1

        return {
            "total": total,
            "passed": passed_count,
            "pass_rate": passed_count / total,
            "avg_faithfulness": sum(r.faithfulness for r in results) / total,
            "avg_relevance": sum(r.relevance for r in results) / total,
            "avg_completeness": sum(r.completeness for r in results) / total,
            "avg_overall": sum(r.overall_score() for r in results) / total,
            "failure_types": failure_types,
        }

    # Completed Task 4: compare averages against baseline and flag drops greater than 0.05.
    def run_regression(self, new_results: list, baseline_results: list) -> dict:
        def avg(items: list[EvalResult], metric: str) -> float:
            return sum(getattr(item, metric) for item in items) / len(items) if items else 0.0

        metrics = ["faithfulness", "relevance", "completeness"]
        new_avgs = {metric: avg(new_results, metric) for metric in metrics}
        baseline_avgs = {metric: avg(baseline_results, metric) for metric in metrics}
        regressions = [
            metric for metric in metrics
            if baseline_avgs[metric] - new_avgs[metric] > 0.05
        ]

        return {
            "new_avg_faithfulness": new_avgs["faithfulness"],
            "new_avg_relevance": new_avgs["relevance"],
            "new_avg_completeness": new_avgs["completeness"],
            "baseline_avg_faithfulness": baseline_avgs["faithfulness"],
            "baseline_avg_relevance": baseline_avgs["relevance"],
            "baseline_avg_completeness": baseline_avgs["completeness"],
            "regressions": regressions,
            "passed": len(regressions) == 0,
        }

    # Completed Task 4: return cases where any answer-side metric is below threshold.
    def identify_failures(
        self,
        results: list[EvalResult],
        threshold: float = 0.5,
    ) -> list[EvalResult]:
        return [
            result for result in results
            if (
                result.faithfulness < threshold
                or result.relevance < threshold
                or result.completeness < threshold
            )
        ]


# Completed Task 5: group failures, infer root causes, and generate improvement actions.
class FailureAnalyzer:
    """Analyzes failed evaluation results and suggests fixes."""

    # Completed Task 5: count failures by failure_type for failure clustering.
    def categorize_failures(
        self, failures: list[EvalResult]
    ) -> dict[str, int]:
        categories: dict[str, int] = {}
        for failure in failures or []:
            key = failure.failure_type or "unknown"
            categories[key] = categories.get(key, 0) + 1
        return categories

    # Completed Task 5: infer root cause from the lowest score pattern.
    def find_root_cause(self, failure: EvalResult) -> str:
        scores = {
            "faithfulness": failure.faithfulness,
            "relevance": failure.relevance,
            "completeness": failure.completeness,
        }
        low_scores = [metric for metric, score in scores.items() if score < 0.4]
        if len(low_scores) >= 2:
            return "Multiple issues detected — review full pipeline"

        lowest_metric = min(scores, key=scores.get)
        if lowest_metric == "faithfulness":
            return "Context is missing or irrelevant — improve retrieval"
        if lowest_metric == "relevance":
            return "Answer does not address the question — improve prompt clarity"
        if lowest_metric == "completeness":
            return "Answer is missing key information — increase context window or improve generation"
        return "Multiple issues detected — review full pipeline"

    # Completed Task 5: produce the Markdown tracking table requested by the README.
    def generate_improvement_log(self, failures: list, suggestions: list[str]) -> str:
        lines = [
            "| Failure ID | Type | Root Cause | Suggested Fix | Status |",
            "|------------|------|------------|---------------|--------|",
        ]

        def clean(value: Any) -> str:
            return str(value).replace("|", "\\|").replace("\n", " ")

        for index, failure in enumerate(failures or [], start=1):
            suggestion = suggestions[index - 1] if index - 1 < len(suggestions or []) else self.find_root_cause(failure)
            lines.append(
                f"| F{index:03d} | {clean(failure.failure_type or 'unknown')} | "
                f"{clean(self.find_root_cause(failure))} | {clean(suggestion)} | Open |"
            )
        return "\n".join(lines)

    # Completed Task 5: generate prioritized, actionable fixes from failure patterns.
    def generate_improvement_suggestions(
        self, failures: list[EvalResult]
    ) -> list[str]:
        if not failures:
            return []

        categories = self.categorize_failures(failures)
        suggestions: list[str] = []

        if categories.get("hallucination", 0) > 0 or any(f.faithfulness < 0.5 for f in failures):
            suggestions.append("Add a faithfulness guardrail and require answers to cite retrieved context before returning.")
        if categories.get("irrelevant", 0) > 0 or categories.get("off_topic", 0) > 0 or any(f.relevance < 0.5 for f in failures):
            suggestions.append("Clarify the system prompt with task scope, refusal rules, and examples for in-scope answers.")
        if categories.get("incomplete", 0) > 0 or any(f.completeness < 0.5 for f in failures):
            suggestions.append("Improve retrieval recall by increasing top-k, tuning chunk size, and adding reranking before generation.")
        if categories.get("refusal", 0) > 0:
            suggestions.append("Relax over-strict guardrails for valid domain questions and add positive examples of answerable requests.")

        generic_suggestions = [
            "Add every confirmed failure to the golden dataset as a permanent regression case.",
            "Track scores per difficulty and category so aggregate pass rate does not hide weak slices.",
            "Run regression evaluation in CI/CD and block deployment when quality drops by more than 0.05.",
        ]
        for suggestion in generic_suggestions:
            if len(suggestions) >= 3:
                break
            suggestions.append(suggestion)

        return suggestions


# Manual smoke test: quick example for running this file directly.
if __name__ == "__main__":
    qa_pairs = [
        QAPair(
            question="What is RAG?",
            expected_answer="RAG stands for Retrieval-Augmented Generation, which combines retrieval with text generation.",
            context="RAG retrieves relevant documents and uses them to ground LLM generation.",
            metadata={"difficulty": "easy", "category": "definition"},
        )
    ]

    evaluator = RAGASEvaluator()
    runner = BenchmarkRunner()
    results = runner.run(qa_pairs, lambda q: "RAG combines retrieval with generation.", evaluator)
    print(runner.generate_report(results))
