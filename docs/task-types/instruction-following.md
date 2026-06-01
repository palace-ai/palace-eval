# Instruction Following Task Type

Instruction Following evaluates whether a model's response satisfies syntactic and structural constraints. Verification is fully deterministic — no LLM judge needed.

## Overview

This task type checks responses against a list of constraints (e.g., word count, forbidden words, format requirements). Each constraint is verified programmatically. The task passes if at least 50% of constraints are satisfied.

**Best for**: Evaluating instruction adherence, format compliance, and controllability.

**Verification**: Deterministic constraint checkers (no API calls).

**Example benchmarks**: IFEval

## How It Works

1. Model receives the objective (instruction prompt)
2. Model generates a response
3. Each constraint is checked independently against the response
4. Score = fraction of constraints satisfied
5. Task passes if score ≥ 0.5

## Configuration

### info.json

```json
{
    "name": "IFEval",
    "id": "google/IFEval",
    "task_type": "Instruction Following",
    "category": "Instruction Following"
}
```

No `task_type_fields` needed at the info level — constraints are per-task.

### tasks.json

Each task has constraints in `task_type_fields`:

```json
{
    "id": "ifeval_001",
    "objective": "Write a poem about the sea. The poem must be exactly 4 paragraphs.",
    "expected": "",
    "task_type_fields": {
        "constraints": [
            {"type": "length_constraints:number_paragraphs", "params": {"num_paragraphs": 4, "relation": "exactly"}},
            {"type": "keywords:existence", "params": {"keywords": ["sea"]}}
        ]
    }
}
```

## Supported Constraints

### Length Constraints

| Type | Params | Description |
|------|--------|-------------|
| `length_constraints:number_words` | `num_words`, `relation` | Word count check |
| `length_constraints:number_sentences` | `num_sentences`, `relation` | Sentence count check |
| `length_constraints:number_paragraphs` | `num_paragraphs`, `relation` | Paragraph count (split on `\n\n`) |
| `length_constraints:nth_paragraph_first_word` | `nth_paragraph`, `first_word` | First word of nth paragraph |

### Keywords

| Type | Params | Description |
|------|--------|-------------|
| `keywords:existence` | `keywords` (list) | All keywords must appear (case-insensitive) |
| `keywords:forbidden_words` | `forbidden_words` (list) | None of the words may appear |
| `keywords:frequency` | `keyword`, `frequency`, `relation` | Keyword occurrence count |
| `keywords:letter_frequency` | `letter`, `let_frequency`, `let_relation` | Letter occurrence count |

### Case

| Type | Params | Description |
|------|--------|-------------|
| `change_case:english_capital` | — | Entire response must be uppercase |
| `change_case:english_lowercase` | — | Entire response must be lowercase |
| `change_case:capital_word_frequency` | `capital_frequency`, `capital_relation` | Percentage of capitalized words |

### Format

| Type | Params | Description |
|------|--------|-------------|
| `detectable_format:json_format` | — | Response must be valid JSON |
| `detectable_format:number_bullet_lists` | `num_bullets`, `relation` | Bullet point count |
| `detectable_format:number_highlighted_sections` | `num_highlights`, `relation` | `*text*` highlight count |
| `detectable_format:multiple_sections` | `section_spliter`, `num_sections`, `relation` | Section count by splitter |
| `detectable_format:title` | — | First line must be a title (markdown heading or all-caps) |
| `detectable_format:constrained_response` | — | Response must be ≤5 words |

### Content

| Type | Params | Description |
|------|--------|-------------|
| `detectable_content:number_placeholders` | `num_placeholders`, `relation` | `[placeholder]` count |
| `detectable_content:postscript` | `postscript_marker` | Must contain postscript marker |
| `punctuation:no_comma` | — | No commas allowed |

### Other

| Type | Params | Description |
|------|--------|-------------|
| `language:response_language` | `language` | Response language check (heuristic) |
| `startend:end_checker` | `end_phrase` | Response must end with phrase |
| `startend:quotation` | — | Response must be wrapped in quotes |
| `combination:repeat_prompt` | `prompt_to_repeat` | Response must contain the prompt |
| `combination:two_responses` | — | Must contain two sections (separated by `***`, `---`, or `===`) |

### Relation Values

The `relation` parameter accepts: `"at least"`, `"at most"`, `"less than"`, `"more than"`, `"exactly"`.

## Metrics

### Aggregate

| Metric | Description |
|--------|-------------|
| `accuracy` | Fraction of tasks where score ≥ 0.5 |
| `avg_score` | Average constraint satisfaction score across all tasks |

### Per-Task

| Metric | Description |
|--------|-------------|
| `score` | Fraction of constraints satisfied (0.0 to 1.0) |
| `satisfied` | Number of constraints satisfied |
| `total` | Total number of constraints |

## Example Output

```
✓ length_constraints:number_paragraphs
✗ keywords:existence
✓ change_case:english_lowercase
Score: 2/3 = 0.6667 → PASS
```

---

## Related Pages

- [Task Types Overview](index.md)
- [Task Type Fields Reference](../reference/task-type-fields.md)
- [Verification Methods](../concepts/verification.md)
