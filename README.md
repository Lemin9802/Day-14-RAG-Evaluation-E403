# Day 14 — AI Evaluation & Benchmarking Pipeline

Repository này triển khai lab **Day 14: AI Evaluation & Benchmarking Pipeline** cho một hệ thống đánh giá AI/RAG assistant. Mục tiêu là xây dựng một evaluation pipeline tự động, có thể chạy benchmark, phân tích lỗi, so sánh framework, và tích hợp vào CI/CD như một quality gate.

## Nội dung đã hoàn thành

- Xây dựng `solution/solution.py` với đầy đủ các component chính:
  - `QAPair` và `EvalResult` cho golden dataset và evaluation result.
  - `RAGASEvaluator` cho các metric: `faithfulness`, `relevance`, `completeness`, `context_recall`, `context_precision`.
  - `rerank_by_overlap()` để cải thiện rank-aware Context Precision.
  - `LLMJudge` dùng rubric scoring 1-5 và normalize về 0-1.
  - `BenchmarkRunner` để chạy benchmark, tạo report, phát hiện regression và lọc failure cases.
  - `FailureAnalyzer` để categorize failures, tìm root cause, tạo improvement suggestions và improvement log.
- Hoàn thành `exercises.md` bằng tiếng Anh với:
  - Warm-up về RAGAS thresholds, LLM-as-Judge bias và CI/CD evaluation.
  - Golden dataset gồm 20 QA pairs: 5 Easy, 7 Medium, 5 Hard, 3 Adversarial.
  - Benchmark results, rubric design, framework comparison và reranking analysis.
- Hoàn thành `reflection.md` bằng tiếng Anh với:
  - Benchmark summary.
  - Top 3 worst failures kèm 5 Whys analysis.
  - Failure clustering, improvement log, regression testing strategy và continuous improvement plan.
- Thêm bonus script `bonus_framework_comparison.py` để so sánh 2 evaluation approaches trên cùng dataset:
  - Framework 1: RAGAS-inspired heuristic evaluator.
  - Framework 2: LLM-as-Judge rubric evaluator với scoring 1-5.
- Thêm `reports/framework_comparison.json` làm output report cho bonus comparison.
- Thêm GitHub Actions workflow tại `.github/workflows/eval.yml` để chạy `pytest tests/ -v` tự động.

## Kết quả kiểm thử

Kết quả local test cuối cùng:

```text
39 passed in 0.05s
```

Kết quả bonus framework comparison:

```json
{
  "framework_1": {
    "name": "RAGAS-inspired heuristic evaluator",
    "results": {
      "pass_rate": 0.8,
      "avg_faithfulness": 0.897,
      "avg_relevance": 0.678,
      "avg_completeness": 0.905,
      "avg_overall": 0.827
    }
  },
  "framework_2": {
    "name": "LLM-as-Judge rubric evaluator, 1-5 scoring normalized to 0-1",
    "results": {
      "pass_rate": 1.0,
      "avg_rubric_score": 0.93,
      "min_rubric_score": 0.85,
      "max_rubric_score": 0.95
    }
  }
}
```

## Cách chạy

Cài và chạy tests:

```bash
python -m pip install pytest
python -m pytest tests/ -v
```

Chạy bonus framework comparison:

```bash
python bonus_framework_comparison.py
```

Script sẽ ghi kết quả vào:

```text
reports/framework_comparison.json
```

## Cấu trúc chính

```text
solution/solution.py                 # Core evaluation pipeline
exercises.md                         # Lab worksheet và benchmark analysis
reflection.md                        # Evaluation report và failure analysis
bonus_framework_comparison.py        # Bonus: compare two evaluation approaches
reports/framework_comparison.json    # Generated comparison report
.github/workflows/eval.yml           # CI/CD quality gate bằng pytest
```

## Tổng kết

Lab này hoàn thiện một automatic evaluation pipeline cho RAG/AI agent, bao gồm offline benchmark, RAGAS-inspired metrics, LLM-as-Judge, regression detection, failure analysis và CI/CD integration. Pipeline đã pass toàn bộ unit tests và có thêm bonus framework comparison để hỗ trợ đánh giá chất lượng theo nhiều góc nhìn.
