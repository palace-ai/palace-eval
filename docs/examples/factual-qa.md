# Factual QA Example

This example demonstrates a simple QA benchmark for testing factual knowledge. It uses the default semantic equivalence criterion, making it easy to set up while still handling varied answer phrasings.

## Use Case

You want to evaluate whether a model can correctly answer factual questions. The challenge: correct answers come in many forms. "Paris", "The capital is Paris", and "Paris, France" all correctly answer "What is the capital of France?"

A simple string match would fail on valid variations. QA with semantic equivalence solves this by using an LLM judge to assess whether the meaning is correct, regardless of phrasing.

## The Tasklist

This example is based on the DocRetrieval-ai benchmark pattern—straightforward factual QA with no custom configuration.

### info.json

```json
{
    "name": "FactualKnowledge",
    "id": "my-org/FactualKnowledge",
    "version": "1.0.0",
    "category": "Knowledge",
    "task_type": "QA"
}
```

That's it. No `task_type_fields` needed. PALACE uses sensible defaults:

- **Criterion**: "semantic equivalence" — the answer must convey the same factual meaning
- **Correct reference**: The `expected` field in each task
- **Incorrect references**: None

### tasks.json

```json
[
    {
        "id": "fact_001",
        "objective": "What is the chemical symbol for gold?",
        "expected": "Au"
    },
    {
        "id": "fact_002",
        "objective": "Who painted the Mona Lisa?",
        "expected": "Leonardo da Vinci"
    },
    {
        "id": "fact_003",
        "objective": "What is the largest planet in our solar system?",
        "expected": "Jupiter"
    },
    {
        "id": "fact_004",
        "objective": "In what year did World War II end?",
        "expected": "1945"
    },
    {
        "id": "fact_005",
        "objective": "What is the speed of light in a vacuum?",
        "expected": "299,792,458 meters per second"
    }
]
```

## How It Works

When you run this benchmark:

1. **Prompt**: The model receives each objective with instructions to provide a direct answer
2. **Response**: The model generates its answer
3. **Judgment**: An LLM judge compares the answer against the `expected` value using semantic equivalence
4. **Result**: The judge outputs "Correct" or "Incorrect" with reasoning

### Example Evaluation

For task `fact_002`:

**Objective**: "Who painted the Mona Lisa?"

**Expected**: "Leonardo da Vinci"

**Model output**: "The Mona Lisa was painted by Leonardo da Vinci, an Italian Renaissance artist."

**Judge reasoning**: "The answer correctly identifies Leonardo da Vinci as the painter of the Mona Lisa. While the response includes additional context about him being an Italian Renaissance artist, the core factual claim matches the reference."

**Result**: ✓ Correct

### Handling Variations

The semantic equivalence criterion handles common variations:

| Model Output | Result | Why |
|--------------|--------|-----|
| "Au" | ✓ | Exact match |
| "The chemical symbol is Au" | ✓ | Same meaning, different phrasing |
| "Gold's symbol is Au (from Latin 'aurum')" | ✓ | Correct with extra context |
| "Ag" | ✗ | Wrong answer (that's silver) |
| "I don't know" | ✗ | Doesn't answer the question |

## Output

Results are saved as JSONL:

```json
{
    "task_id": "fact_001",
    "objective": "What is the chemical symbol for gold?",
    "expected": "Au",
    "model_output": "The chemical symbol for gold is Au.",
    "is_correct": true,
    "reasoning": "The answer correctly states that Au is the chemical symbol for gold, matching the reference answer.",
    "metrics": {
        "criterion": "semantic equivalence"
    }
}
```

## Customization Ideas

### Different Domains

Adapt this pattern for any factual domain:

**Science**:
```json
{"objective": "What is the atomic number of carbon?", "expected": "6"}
```

**History**:
```json
{"objective": "Who was the first President of the United States?", "expected": "George Washington"}
```

**Geography**:
```json
{"objective": "What is the longest river in the world?", "expected": "The Nile"}
```

### Stricter Criteria

If you need more specific matching, customize the criterion:

```json
{
    "task_type_fields": {
        "correctness_criterion": {
            "name": "exact factual match",
            "description": "The answer must contain the exact fact requested, with no incorrect additional claims. Extra context is acceptable only if accurate."
        }
    }
}
```

### Adding Difficulty Levels

Track task difficulty for analysis:

```json
{
    "id": "fact_hard_001",
    "objective": "What is the half-life of Carbon-14?",
    "expected": "5,730 years",
    "difficulty": "hard"
}
```

The `difficulty` field is preserved in results for filtering and analysis.

## When to Use This Pattern

This simple QA pattern works well when:

- Answers are factual and verifiable
- Multiple phrasings are acceptable
- You don't need to distinguish between types of wrong answers
- Speed of setup matters more than nuanced evaluation

For more complex scenarios, consider:

- **Custom criteria** — When you need specific evaluation logic
- **Incorrect references** — When you want to catch specific failure modes
- **Classification** — When answers must match exactly

---

## Related Pages

- [QA Task Type](../task-types/qa.md) — Full QA documentation
- [Sycophancy Example](sycophancy.md) — QA with custom criteria and incorrect references
- [Your First Benchmark](../getting-started/first-benchmark.md) — Step-by-step tutorial
