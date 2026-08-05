# DeepResearchBench

DeepResearchBench is an advanced report generation benchmark that evaluates research report quality using task-specific hierarchical evaluation criteria. Unlike DeepConsult which uses default criteria, each DeepResearchBench task defines its own evaluation rubric with weighted dimensions and nested criteria, enabling nuanced assessment tailored to each research question.

## Overview

| Property | Value |
|----------|-------|
| **Task Type** | Criteria Evaluation |
| **Category** | Deep Research |
| **Total Tasks** | 50 |
| **Evaluation** | Per-task hierarchical criteria |
| **Dimensions** | 4 (readability, insight, comprehensiveness, instruction_following) |

## Purpose and Motivation

Research reports vary significantly in their requirements—a market analysis report needs different qualities than a technical literature review. DeepResearchBench addresses this by:

- **Task-specific evaluation**: Each task defines exactly what qualities matter for that particular research question
- **Hierarchical criteria**: Dimensions contain weighted sub-criteria for granular assessment
- **Weighted scoring**: Different aspects can be weighted according to their importance
- **Comprehensive rubrics**: Detailed descriptions guide consistent evaluation

This makes DeepResearchBench particularly valuable for understanding not just whether a model can generate good reports, but specifically which aspects of report quality it excels at or struggles with.

## Data Composition

### Research Topics

DeepResearchBench covers complex research questions requiring comprehensive analysis:

- **Market analysis**: Demographic trends, consumer behavior, market sizing
- **Investment research**: Fund strategies, risk assessment, portfolio analysis
- **Policy analysis**: Regulatory impacts, economic forecasting
- **Technology assessment**: Emerging tech evaluation, adoption patterns
- **Strategic planning**: Business strategy, competitive positioning

### Task Structure

Each task includes the research question, a reference report, and a complete evaluation rubric:

```json
{
    "id": "DeepResearchBench_DRB_51",
    "objective": "From 2020 to 2050, how many elderly people will there be in Japan? What is their consumption potential across various aspects such as clothing, food, housing, and transportation? Based on population projections, elderly consumer willingness, and potential changes in their consumption habits, please produce a market size analysis report for the elderly demographic.",
    "expected": "# Japan's Silver Tsunami: Market Size Analysis...\n\n## Executive Summary\n...",
    "task_type_fields": {
        "dimensions": [
            {
                "name": "readability",
                "weight": 0.15,
                "criteria": [...]
            },
            {
                "name": "insight",
                "weight": 0.33,
                "criteria": [...]
            },
            {
                "name": "comprehensiveness",
                "weight": 0.30,
                "criteria": [...]
            },
            {
                "name": "instruction_following",
                "weight": 0.22,
                "criteria": [...]
            }
        ]
    }
}
```

### Evaluation Dimensions

Each task defines four evaluation dimensions with different weights:

| Dimension | Typical Weight | Focus |
|-----------|---------------|-------|
| **Readability** | 0.15 | Structure, clarity, presentation |
| **Insight** | 0.33 | Depth, originality, analytical rigor |
| **Comprehensiveness** | 0.30 | Coverage, thoroughness, completeness |
| **Instruction Following** | 0.22 | Adherence to specific requirements |

### Hierarchical Criteria

Each dimension contains multiple weighted criteria. For example, the **readability** dimension might include:

```json
{
    "name": "readability",
    "weight": 0.15,
    "criteria": [
        {
            "name": "overall_structure_navigability",
            "description": "Assesses if the report has a clear, logical structure with distinct, well-labeled heading levels.",
            "weight": 0.2
        },
        {
            "name": "clarity_precision_professionalism_language",
            "description": "Evaluates if the language is fluent, grammatically correct, unambiguous, and uses precise terminology.",
            "weight": 0.2
        },
        {
            "name": "clarity_quantitative_data_presentation_text",
            "description": "Evaluates how clearly numerical data are presented and contextualized within the narrative.",
            "weight": 0.15
        },
        {
            "name": "effectiveness_clarity_visualizations",
            "description": "Assesses if charts and tables are used effectively to illustrate trends and comparisons.",
            "weight": 0.15
        },
        {
            "name": "paragraph_cohesion_smooth_transitions",
            "description": "Assesses if transitions between paragraphs and sections are smooth and logical.",
            "weight": 0.1
        },
        {
            "name": "audience_adaptation_explanation_terms",
            "description": "Evaluates if terminology and explanations are appropriate for the target audience.",
            "weight": 0.1
        },
        {
            "name": "conciseness_focus",
            "description": "Evaluates if the report is free of unnecessary jargon and redundancy.",
            "weight": 0.05
        },
        {
            "name": "formatting_layout_visual_appeal",
            "description": "Assesses if the document's layout contributes to professional appearance.",
            "weight": 0.05
        }
    ]
}
```

## Configuration

```json
{
    "name": "DeepResearchBench",
    "id": "jrc-ai/DeepResearchBench",
    "version": "1.0.0",
    "original": true,
    "category": "Deep Research",
    "task_type": "Criteria Evaluation",
    "task_type_fields": {
        "per_task_criteria": true
    }
}
```

The `per_task_criteria: true` flag indicates that evaluation criteria are defined at the task level rather than the tasklist level.

## Evaluation Methodology

DeepResearchBench uses hierarchical LLM-based evaluation:

### Scoring Process

1. **Report generation**: The model generates a comprehensive research report
2. **Pairwise comparison**: An LLM judge compares against the reference report
3. **Per-criterion evaluation**: The judge assesses each criterion within each dimension
4. **Weighted aggregation**: Scores are combined using the defined weights

### Score Calculation

The final score is calculated hierarchically:

```
Dimension Score = Σ (criterion_weight × criterion_score) for all criteria in dimension
Overall Score = Σ (dimension_weight × dimension_score) for all dimensions
```

For example, if a report scores:
- Readability: 0.8 (weight 0.15)
- Insight: 0.7 (weight 0.33)
- Comprehensiveness: 0.75 (weight 0.30)
- Instruction Following: 0.85 (weight 0.22)

Overall = (0.15 × 0.8) + (0.33 × 0.7) + (0.30 × 0.75) + (0.22 × 0.85) = 0.763

### Normalized Scoring

The pairwise comparison produces a normalized score based on the gap between the generated report and the reference:

- **Score = 1.0**: Generated report is clearly better
- **Score = 0.5**: Reports are roughly equivalent
- **Score = 0.0**: Reference report is clearly better

## Running Evaluations

```bash
# Download the tasklist
palace download DeepResearchBench

# Run evaluation (generates long reports with detailed scoring)
palace run DeepResearchBench -m gpt-4o -l 5

# Run with smaller limit to inspect per-criterion scores
palace run DeepResearchBench -m gpt-4o -l 3
```

### Considerations

- **Evaluation complexity**: Hierarchical criteria require more judge calls
- **Generation time**: Research reports are lengthy (5,000–20,000+ words)
- **Token usage**: Both generation and multi-criterion evaluation are token-intensive

## Interpreting Results

### Metrics

- **Overall score**: Weighted aggregate across all dimensions
- **Per-dimension scores**: Performance on readability, insight, comprehensiveness, instruction following
- **Per-criterion breakdown**: Detailed scores for each sub-criterion
- **Score distribution**: Variance across tasks

### What to Look For

- **Dimension patterns**: Which dimensions does the model excel at or struggle with?
- **Criterion-level insights**: Are there specific criteria that consistently score low?
- **Task-type patterns**: Does performance vary by research topic type?
- **Consistency**: How much variance is there across tasks?

### Example Output

```
Task: DeepResearchBench_DRB_51 (Japan elderly market analysis)

Dimensions:
  readability (0.15):        0.82
    - overall_structure:     0.85
    - clarity_language:      0.80
    - data_presentation:     0.78
    - visualizations:        0.75
    - transitions:           0.88
    - audience_adaptation:   0.82
    - conciseness:           0.85
    - formatting:            0.80
    
  insight (0.33):            0.71
    - depth_originality:     0.68
    - logical_rigor:         0.75
    - nuanced_analysis:      0.70
    - interpretation:        0.72
    - strategic_value:       0.70
    
  comprehensiveness (0.30):  0.76
    - population_projections: 0.80
    - consumption_analysis:   0.75
    - market_sizing:          0.72
    - methodology:            0.78
    
  instruction_following (0.22): 0.85
    - format_adherence:       0.88
    - scope_coverage:         0.82
    - specific_requirements:  0.85

Overall Score: 0.77
```

## Use Cases

- **Detailed capability assessment**: Understanding specific strengths and weaknesses
- **Model comparison**: Comparing models on specific quality dimensions
- **Training feedback**: Identifying areas for model improvement
- **Quality assurance**: Setting thresholds for production deployment

## Comparison with DeepConsult

| Aspect | DeepConsult | DeepResearchBench |
|--------|-------------|-------------------|
| **Tasks** | 102 | 50 |
| **Criteria** | Default (tasklist-level) | Per-task hierarchical |
| **Evaluation depth** | Standard pairwise | Multi-dimensional with sub-criteria |
| **Use case** | General report quality | Detailed quality analysis |
| **Evaluation cost** | Lower | Higher (more judge calls) |

## Limitations

- **Evaluation cost**: Hierarchical criteria require more computation
- **Rubric subjectivity**: Criteria definitions involve interpretation
- **Reference dependency**: Scores are relative to reference reports
- **Task count**: 50 tasks may not cover all research domains

---

## Related Pages

- [Criteria Evaluation Task Type](../../task-types/criteria-evaluation.md) — How report generation evaluation works
- [Hierarchical Criteria Guide](../../howto/custom-criteria.md) — Defining custom evaluation criteria
- [DeepConsult](deepconsult.md) — Simpler report generation benchmark
- [Official Tasklists Overview](index.md) — All official PALACE tasklists
