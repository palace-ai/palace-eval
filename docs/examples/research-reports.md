# Research Reports Example

This example demonstrates evaluating long-form research reports using the Report Generation task type. It's based on the DeepResearchBench pattern—hierarchical criteria organized into dimensions for comprehensive quality assessment.

## Use Case

You want to evaluate whether a model can produce high-quality research reports. Unlike simple QA where answers are short and factual, research reports require:

- Comprehensive coverage of the topic
- Logical organization and clear structure
- Accurate information and sound analysis
- Quality writing and appropriate depth

A single "correct/incorrect" judgment can't capture this complexity. Report Generation uses multiple weighted criteria to assess different quality dimensions, providing nuanced scores and actionable feedback.

## The Tasklist

This example follows the DeepResearchBench structure with hierarchical dimensions.

### info.json

```json
{
    "name": "ResearchReportBench",
    "id": "my-org/ResearchReportBench",
    "version": "1.0.0",
    "category": "Deep Research",
    "task_type": "Report Generation",
    "task_type_fields": {
        "dimensions": [
            {
                "name": "content_quality",
                "weight": 0.5,
                "criteria": [
                    {
                        "name": "accuracy",
                        "description": "Factual correctness of claims, proper use of data, and absence of misinformation.",
                        "weight": 0.4
                    },
                    {
                        "name": "comprehensiveness",
                        "description": "Breadth of coverage across relevant topics and subtopics.",
                        "weight": 0.3
                    },
                    {
                        "name": "depth",
                        "description": "Level of detail and thoroughness in analyzing each topic.",
                        "weight": 0.3
                    }
                ]
            },
            {
                "name": "presentation",
                "weight": 0.3,
                "criteria": [
                    {
                        "name": "structure",
                        "description": "Logical organization with clear sections, headings, and flow.",
                        "weight": 0.5
                    },
                    {
                        "name": "clarity",
                        "description": "Clear, precise language that effectively communicates complex ideas.",
                        "weight": 0.5
                    }
                ]
            },
            {
                "name": "insight",
                "weight": 0.2,
                "criteria": [
                    {
                        "name": "analysis",
                        "description": "Quality of reasoning, synthesis of information, and drawing of conclusions.",
                        "weight": 0.6
                    },
                    {
                        "name": "actionability",
                        "description": "Practical recommendations that readers can implement.",
                        "weight": 0.4
                    }
                ]
            }
        ]
    }
}
```

### Understanding the Hierarchy

This configuration creates a two-level structure:

**Dimensions** (top level):
- `content_quality` (50% of total score)
- `presentation` (30% of total score)
- `insight` (20% of total score)

**Criteria** (within each dimension):
- Each dimension contains specific criteria
- Criteria weights are relative within their dimension

**Effective weights** (dimension × criterion):
- `accuracy`: 0.5 × 0.4 = 0.20 (20% of total)
- `comprehensiveness`: 0.5 × 0.3 = 0.15 (15% of total)
- `depth`: 0.5 × 0.3 = 0.15 (15% of total)
- `structure`: 0.3 × 0.5 = 0.15 (15% of total)
- `clarity`: 0.3 × 0.5 = 0.15 (15% of total)
- `analysis`: 0.2 × 0.6 = 0.12 (12% of total)
- `actionability`: 0.2 × 0.4 = 0.08 (8% of total)

### tasks.json

```json
[
    {
        "id": "report_001",
        "objective": "Write a comprehensive report analyzing the impact of artificial intelligence on the job market over the next decade. Include current trends, projected changes by industry, potential policy responses, and recommendations for workers and employers.",
        "expected": "# AI and the Future of Work: A Comprehensive Analysis\n\n## Executive Summary\n\nArtificial intelligence is reshaping the global job market...\n\n## Current State of AI in the Workplace\n\n### Automation Trends\n...\n\n## Industry-Specific Projections\n\n### Manufacturing\n...\n\n### Healthcare\n...\n\n## Policy Considerations\n\n...\n\n## Recommendations\n\n### For Workers\n...\n\n### For Employers\n...\n\n## Conclusion\n..."
    },
    {
        "id": "report_002",
        "objective": "Produce a market analysis report on the electric vehicle industry in Europe. Cover market size, key players, regulatory environment, consumer trends, and growth projections through 2030.",
        "expected": "# European Electric Vehicle Market Analysis\n\n## Market Overview\n\n...\n\n## Competitive Landscape\n\n...\n\n## Regulatory Framework\n\n...\n\n## Consumer Behavior\n\n...\n\n## Growth Projections\n\n...\n\n## Strategic Recommendations\n..."
    }
]
```

The `expected` field contains a reference report that the model's output will be compared against.

## How It Works

Report Generation uses pairwise comparison:

1. **Model generates report** from the objective prompt
2. **Judge compares** the generated report against the reference
3. **For each criterion**, the judge decides which report is better and by how much
4. **Position bias mitigation**: Comparison runs twice with reports swapped
5. **Scores aggregate** across criteria using the configured weights
6. **Task passes** if the generated report outscores the reference

### Scoring

For each criterion, the judge assigns a gap score (0-5) indicating the quality difference, along with which report is better. After running both comparisons (AB and BA), scores are combined into a per-criterion score ranging from -10 to +10:

| Per-Criterion Score | Meaning |
|---------------------|---------|
| +10 | Generated report is much better |
| +5 | Generated report is moderately better |
| 0 | Reports are equivalent |
| -5 | Reference report is moderately better |
| -10 | Reference report is much better |

## Output

Results include detailed scoring. Each task in `detailed_report` contains:

```json
{
    "objective": "Write a comprehensive report analyzing...",
    "expected": "# AI and the Future of Work...",
    "actual": "# Generated Report...",
    "is_correct": true,
    "reasoning": "## accuracy (+2)\n...\n## Summary\n...",
    "elapsed_time": 45.2,
    "metrics": {
        "criteria_scores": {
            "accuracy": 2,
            "comprehensiveness": 1,
            "depth": 3,
            "structure": 0,
            "clarity": 2,
            "analysis": 4,
            "actionability": 1
        },
        "dimension_scores": {
            "content_quality": 6,
            "presentation": 2,
            "insight": 5
        },
        "overall_gap": 8.5,
        "normalized_score": 0.68,
        "score_provided": 12.0,
        "score_expected": 3.5
    }
}
```

This is the structure for a single task within the `detailed_report` object, keyed by task ID (e.g., `"report_001": {...}`).

### Interpreting Scores

- **criteria_scores**: Per-criterion comparison (-10 to +10)
- **dimension_scores**: Aggregated scores per dimension
- **overall_gap**: Weighted sum of all criteria scores
- **normalized_score**: Gap rescaled to [0, 1] where 0.5 = tie
- **is_correct**: True if generated report scored higher overall

## Per-Task Criteria

For benchmarks where different reports need different evaluation criteria, enable per-task customization:

### info.json

```json
{
    "task_type_fields": {
        "dimensions": [...],
        "per_task_criteria": true
    }
}
```

### tasks.json

```json
{
    "id": "financial_report",
    "objective": "Write a quarterly financial analysis...",
    "expected": "...",
    "task_type_fields": {
        "dimensions": [
            {
                "name": "financial_rigor",
                "weight": 0.4,
                "criteria": [
                    {
                        "name": "numerical_accuracy",
                        "description": "All calculations, percentages, and financial figures are correct.",
                        "weight": 1.0
                    }
                ]
            }
        ]
    }
}
```

Task-level dimensions merge with tasklist-level dimensions:
- New dimension names are added
- Same dimension names override the tasklist configuration

## Designing Criteria

### Be Specific

❌ **Vague**: "Quality of the report"

✅ **Specific**: "Factual correctness of claims, proper use of data, and absence of misinformation"

### Match Your Domain

**Technical reports**:
```json
{"name": "technical_accuracy", "description": "Correct use of technical terminology, accurate specifications, and valid technical claims."}
```

**Business reports**:
```json
{"name": "market_insight", "description": "Demonstrates understanding of market dynamics, competitive landscape, and business implications."}
```

**Academic reports**:
```json
{"name": "citation_quality", "description": "Proper attribution of sources, appropriate use of references, and scholarly rigor."}
```

### Balance Weights

- **High weight (0.4-0.6)**: Core requirements for your use case
- **Medium weight (0.2-0.3)**: Important but secondary factors
- **Low weight (0.1-0.2)**: Nice-to-have qualities

## Customization Ideas

### Flat Criteria (No Dimensions)

For simpler evaluation, use flat criteria without dimensions:

```json
{
    "task_type_fields": {
        "criteria": [
            {"name": "accuracy", "description": "...", "weight": 2.0},
            {"name": "completeness", "description": "...", "weight": 1.5},
            {"name": "clarity", "description": "...", "weight": 1.0}
        ]
    }
}
```

### Domain-Specific Dimensions

**Legal documents**:
```json
{
    "dimensions": [
        {"name": "legal_accuracy", "weight": 0.4, "criteria": [...]},
        {"name": "compliance", "weight": 0.3, "criteria": [...]},
        {"name": "clarity", "weight": 0.3, "criteria": [...]}
    ]
}
```

**Scientific papers**:
```json
{
    "dimensions": [
        {"name": "methodology", "weight": 0.3, "criteria": [...]},
        {"name": "results", "weight": 0.3, "criteria": [...]},
        {"name": "discussion", "weight": 0.2, "criteria": [...]},
        {"name": "presentation", "weight": 0.2, "criteria": [...]}
    ]
}
```

## When to Use This Pattern

Report Generation works well when:

- Evaluating long-form written content
- Multiple quality dimensions matter
- You have reference documents for comparison
- You need detailed, actionable feedback

For simpler evaluations, consider:

- **QA** — For short factual answers
- **Classification** — For categorical judgments about content

---

## Related Pages

- [Report Generation Task Type](../task-types/report-generation.md) — Full documentation
- [Task Type Fields Reference](../reference/task-type-fields.md) — Complete field specification
- [Custom Criteria Guide](../howto/custom-criteria.md) — Designing evaluation criteria
