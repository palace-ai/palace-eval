# Verification Methods

This page explains the different ways PALACE verifies model outputs and when to use each approach.

## Overview

PALACE supports three verification methods, each suited to different evaluation scenarios:

| Method | Task Type | Speed | Flexibility |
|--------|-----------|-------|-------------|
| LLM Judge | QA | Slower | High |
| Exact Match | Classification | Fast | Low |
| Pairwise Comparison | Criteria Evaluation | Slower | High |
| Constraint Checkers | Instruction Following | Fast | Medium |
| Absolute Rubric | Criteria Evaluation | Slower | High |

## LLM Judge Verification (QA)

An LLM evaluates whether the model's answer satisfies a criterion when compared to reference answers.

### How It Works

1. Construct judge prompt with criterion, references, and model answer
2. Send to judge LLM
3. Parse judge's reasoning and verdict
4. Return Correct or Incorrect

### Strengths

- **Semantic understanding**: Handles paraphrasing, synonyms, varied phrasing
- **Configurable criteria**: Define what "correct" means for your use case
- **Detailed reasoning**: Judge explains its decision

### Limitations

- **Slower**: Requires additional API call per task
- **Cost**: Judge calls add to API usage
- **Variability**: Judge decisions may vary slightly between runs

### When to Use

- Answers can be phrased many ways
- Semantic equivalence matters more than exact wording
- You need nuanced evaluation criteria

### Configuration

```json
{
    "task_type": "QA",
    "task_type_fields": {
        "correctness_criterion": {
            "name": "semantic equivalence",
            "description": "The answer conveys the same factual meaning."
        }
    }
}
```

## Exact Match Verification (Classification)

The model's output is parsed and compared exactly against expected values.

### How It Works

1. Parse XML tags from model output
2. Extract value for each label
3. Compare string-to-string against expected
4. All labels must match exactly

### Strengths

- **Fast**: No API calls for verification
- **Deterministic**: Same input always gives same result
- **Simple**: Easy to understand and debug

### Limitations

- **Rigid**: No tolerance for variations (leading/trailing whitespace is stripped, but comparison is otherwise exact)
- **Format-dependent**: Model must use exact XML format
- **Case-sensitive**: "Yes" ≠ "yes"

### When to Use

- Fixed set of valid outputs
- Exact matching is appropriate
- Speed and determinism matter
- Building classifiers or filters

### Configuration

```json
{
    "task_type": "Classification",
    "task_type_fields": {
        "labels": [
            {
                "name": "Category",
                "classes": [
                    {"name": "A", "condition": "..."},
                    {"name": "B", "condition": "..."}
                ]
            }
        ]
    }
}
```

## Pairwise Comparison (Criteria Evaluation)

An LLM compares the model's output against a reference document across multiple criteria.

### How It Works

1. Present both reports to judge (generated vs reference)
2. For each criterion, judge decides which is better
3. Judge assigns gap score (0 to 5) per criterion indicating quality difference
4. Run comparison twice with positions swapped (reduces bias)
5. Aggregate weighted scores into per-criterion scores (range -10 to +10)
6. Task passes if generated report scores higher

### Strengths

- **Multi-dimensional**: Evaluates multiple quality aspects
- **Weighted**: Prioritize what matters most
- **Nuanced**: Captures degrees of quality, not just pass/fail
- **Bias mitigation**: Position swapping reduces order effects

### Limitations

- **Slowest**: Multiple judge calls per task
- **Complex**: More configuration required
- **Reference-dependent**: Quality of reference affects evaluation

### When to Use

- Evaluating long-form content
- Multiple quality dimensions matter
- You have good reference documents
- Detailed scoring is valuable

### Configuration

```json
{
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "criteria": [
            {"name": "accuracy", "description": "...", "weight": 2.0},
            {"name": "clarity", "description": "...", "weight": 1.0}
        ]
    }
}
```

## Comparison

### Speed

```
Classification (Exact Match)  ████████████████████  Fastest
QA (LLM Judge)               ████████              Medium
Criteria Evaluation (Pairwise)  ████                  Slowest
```

### Flexibility

```
Criteria Evaluation (Pairwise)  ████████████████████  Most Flexible
QA (LLM Judge)               ████████████████      Flexible
Classification (Exact Match)  ████                  Rigid
```

### Use Case Fit

| Scenario | Best Method |
|----------|-------------|
| Factual QA with varied phrasing | LLM Judge |
| Safety classification | Exact Match |
| Content moderation | Exact Match |
| Research report quality | Pairwise Comparison |
| Sentiment analysis | Exact Match |
| Sycophancy detection | LLM Judge |
| Document summarization | Pairwise Comparison |

## Choosing a Method

### Decision Flow

1. **Is output categorical?** → Classification (Exact Match)
2. **Is output long-form?** → Criteria Evaluation (Pairwise)
3. **Otherwise** → QA (LLM Judge)

### Trade-offs

| Priority | Choose |
|----------|--------|
| Speed | Classification or Instruction Following |
| Flexibility | QA or Criteria Evaluation |
| Determinism | Classification or Instruction Following |
| Nuanced scoring | Criteria Evaluation |
| Simple setup | QA (default criterion) |
| No reference needed | Instruction Following or Criteria Evaluation |

---

## Constraint Verification (Instruction Following)

Deterministic checkers verify structural properties of the response without any LLM calls.

### How It Works

1. Each task defines a list of constraints (type + params)
2. Each constraint is checked independently against the response
3. Score = fraction of constraints satisfied
4. Task passes if score ≥ 0.5

### Strengths

- **Fast**: No API calls needed
- **Deterministic**: Same input always gives same result
- **Transparent**: Each constraint result is visible

### Limitations

- **Structural only**: Cannot assess semantic quality
- **Fixed set**: Only supports predefined constraint types

### When to Use

- Evaluating format compliance (word count, JSON, bullet lists)
- Testing controllability (forbidden words, case requirements)
- Need reproducible, fast verification

## Absolute Rubric Verification (Criteria Evaluation)

An LLM judge evaluates each criterion independently as met or not met, without comparing against a reference.

### How It Works

1. Present the question and response to the judge
2. For each criterion, judge decides YES (met) or NO (not met)
3. Points are tallied: positive for met rewards, negative for met penalties
4. Score = earned / max_positive, clamped to [0, 1]
5. Task passes if score ≥ 0.5

### Strengths

- **No reference needed**: Evaluates against a rubric, not a gold answer
- **Granular scoring**: Per-criterion and per-dimension breakdowns
- **Penalty support**: Negative points for undesirable behaviors

### Limitations

- **Slower**: Requires LLM judge calls (batched for efficiency)
- **Cost**: Judge calls add to API usage

### When to Use

- Rubric-based evaluation (medical, educational)
- No reference document available
- Need penalty scoring for bad behaviors
- Want per-dimension quality breakdowns

---

## Related Pages

- [Evaluation Pipeline](evaluation-pipeline.md) — End-to-end flow
- [LLM Judges](llm-judges.md) — How judges work
- [Task Types](../task-types/index.md) — Task type details
