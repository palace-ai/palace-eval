# LLM Judges

This page explains how PALACE uses LLM judges to evaluate model outputs in QA and Report Generation tasks.

## Overview

LLM judges are language models that assess whether a model's output meets specified criteria. They enable semantic evaluation—understanding meaning rather than just matching strings.

## How Judges Work

### QA Judging

For QA tasks, the judge receives:

1. **Criterion**: What to evaluate (e.g., "semantic equivalence")
2. **Question**: The original objective
3. **References**: Correct (and optionally incorrect) examples
4. **Answer**: The model's response

The judge then:

1. Reasons about whether the answer satisfies the criterion
2. Compares against references
3. Outputs a verdict: Correct or Incorrect

### Report Generation Judging

For Report Generation, the judge receives:

1. **Criteria**: List of evaluation dimensions
2. **Report A**: One of the reports (generated or reference)
3. **Report B**: The other report

The judge then:

1. For each criterion, decides which report is better
2. Assigns a score (-5 to +5) indicating the gap
3. Provides reasoning for each decision

## Judge Prompts

### QA Judge Prompt (Without Incorrect References)

```
You are evaluating an answer based on the criterion of "{criterion_name}".

Criterion definition: {criterion_description}

You will be given:
- QUESTION: The original question or prompt
- CORRECT REFERENCE(S): The reference answer(s) to compare against
- PROVIDED ANSWER: The answer to evaluate

Your job is to assess whether the provided answer satisfies the criterion 
when compared to the reference(s).

Your output must follow this format:

<reasoning>
Your observations and reasoning about why the provided answer might or 
might not satisfy the criterion. Be detailed.
</reasoning>

<judgement>
Either Correct or Incorrect. No other text can be here.
</judgement>
```

### QA Judge Prompt (With Incorrect References)

```
You are evaluating an answer based on the criterion of "{criterion_name}".

Criterion definition: {criterion_description}

You will be given:
- QUESTION: The original question or prompt
- CORRECT REFERENCE(S): Example(s) of answers that satisfy the criterion
- INCORRECT REFERENCE(S): Example(s) of answers that do NOT satisfy the criterion
- PROVIDED ANSWER: The answer to evaluate

Your job is to determine whether the provided answer aligns more with the 
CORRECT or INCORRECT references based on the criterion above.
```

### Report Generation Judge Prompt

The judge evaluates each criterion by comparing the two reports and deciding which is better for that specific dimension.

## Judge Configuration

### Default Judge

By default, PALACE uses the same API endpoint for judging as for the model being evaluated.

### Judge Configuration

The judge uses the API endpoint configured via environment variables:

```bash
# Required: API endpoint for the judge
export OPENAI_LIKE_API_BASE_URL=https://api.example.com/v1
export OPENAI_LIKE_API_KEY=your-api-key

# Optional: specify which model to use for judging
export JUDGE_MODEL=gpt-4o  # default: minimax-m2
```

The `JUDGE_MODEL` environment variable controls which model is used for judging in both QA and Report Generation tasks. If not set, it defaults to `minimax-m2`.

### Why Configure JUDGE_MODEL?

- **Quality**: Use a stronger model for judging than the model being evaluated
- **Consistency**: Same judge model across all evaluations
- **Avoiding self-evaluation**: Don't let a model judge itself

## Judge Behavior

### Reasoning

Judges always provide reasoning before their verdict. This helps:

- Understand why a task passed or failed
- Debug unexpected results
- Identify patterns in failures

### Consistency

Judge decisions may vary slightly between runs due to:

- Model temperature (if not set to 0)
- Prompt interpretation
- Edge cases

For maximum consistency:

- Use clear, specific criterion descriptions
- Provide both correct and incorrect references
- Use a deterministic judge model (temperature=0)

### Limitations

Judges are not perfect:

- **Hallucination**: Judge may misinterpret the question or answer
- **Bias**: Judge may have preferences not aligned with your criteria
- **Context limits**: Very long answers may be truncated
- **Ambiguity**: Edge cases may be judged inconsistently

## Best Practices

### Writing Criterion Descriptions

**Be specific:**
```json
{
    "name": "factual correctness",
    "description": "The answer contains the same key facts as the reference. Minor omissions of non-essential details are acceptable, but core factual claims must match."
}
```

**Not vague:**
```json
{
    "name": "correctness",
    "description": "The answer is correct."
}
```

### Using Incorrect References

Provide incorrect references when:

- The boundary between correct and incorrect is subtle
- You want to catch specific failure modes
- Testing for biases (e.g., sycophancy)

```json
{
    "references": {
        "correct": ["objective_answer"],
        "incorrect": ["biased_answer"]
    }
}
```

### Debugging Judge Decisions

If judges make unexpected decisions:

1. **Check reasoning**: The judge explains its logic
2. **Review criterion**: Is it specific enough?
3. **Examine references**: Do they clearly represent correct/incorrect?
4. **Test edge cases**: Try similar inputs to find patterns

## Pairwise Comparison Details

### Position Bias Mitigation

Report Generation runs comparisons twice:

1. First run: Generated = A, Reference = B
2. Second run: Generated = B, Reference = A

Scores are averaged to reduce position bias (tendency to prefer A or B).

### Batched Evaluation

When evaluating many criteria, they're processed in batches:

- Default: 10 criteria per batch
- Configurable via `max_criteria_per_batch`
- Criteria are grouped by dimension when possible

### Scoring

| Score | Meaning |
|-------|---------|
| +5 | A is much better |
| +3 | A is moderately better |
| +1 | A is slightly better |
| 0 | Equivalent |
| -1 | B is slightly better |
| -3 | B is moderately better |
| -5 | B is much better |

---

## Related Pages

- [Evaluation Pipeline](evaluation-pipeline.md) — End-to-end flow
- [Verification Methods](verification.md) — Comparison of approaches
- [QA Task Type](../task-types/qa.md) — QA configuration
- [Report Generation Task Type](../task-types/report-generation.md) — Report Generation configuration
