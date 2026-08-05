# Model Adapters

Some models are highly specialized — finetuned guardrail models, for example, expect raw user text as input and produce fixed-format output like `"User Safety: unsafe"`. They cannot follow PALACE's prompt formatting instructions, and they cannot produce the structured output that task types expect for verification.

Model Adapters solve this by letting you define per-model input/output transformations. The same tasklist works with both general-purpose models (which follow PALACE's instructions) and specialized models (which need adapted I/O).

## The Problem

Consider evaluating a guardrail model on GuardBench-EN. Without an adapter:

1. PALACE sends the full Classification prompt: *"You have to perform a classification task. Consider the following text: HeLlO rEtArD. And consider the following labels..."*
2. The guardrail model interprets **all of that** as user input to classify
3. It outputs `"safe"` (because the text looks like instructions, not harmful content)
4. PALACE looks for `<Unsafe>Yes</Unsafe>` in the output — doesn't find it — marks incorrect

With an adapter, you tell PALACE: "For this model, just send the raw text, and parse `safe`/`unsafe` from the output."

## Quick Start

Create the adapters file:

```bash
mkdir -p ~/.config/palace
```

```yaml
# ~/.config/palace/io_adapters.yaml

"llamaguard-*":
  input:
    template: "{objective}"
  output:
    pattern: "(?P<result>safe|unsafe)"
    template: "<Unsafe>{result}</Unsafe>"
    mapping:
      result:
        safe: "No"
        unsafe: "Yes"
```

Run the evaluation as normal:

```bash
palace run llamaguard-7b -m GuardBench-EN -l 3
```

PALACE matches `llamaguard-7b` against the `llamaguard-*` glob pattern, applies the adapter, and the evaluation works correctly.

## Configuration File

Adapters are defined in a YAML file at:

```
~/.config/palace/io_adapters.yaml
```

On Linux, this resolves to `/home/<user>/.config/palace/io_adapters.yaml`. The file is optional — if it doesn't exist, PALACE uses default behavior.

## Bundled Adapters

PALACE ships with pre-configured adapters for popular specialized models (guardrails, safety classifiers, etc.) inside the package. These work out of the box — no configuration needed.

When you evaluate a model, PALACE checks your local adapter file first, then falls back to bundled adapters. This means bundled adapters activate automatically for supported models, but you can always override them.

### Overriding a Bundled Adapter

Add a matching glob pattern to your local `io_adapters.yaml`. Your entry takes priority over the bundled one:

```yaml
# ~/.config/palace/io_adapters.yaml

# Override bundled adapter with custom output parsing
"granite-guardian-*":
  input:
    template: "{objective}"
  output:
    pattern: "(?P<result>Yes|No|safe|unsafe)"
    mapping:
      result:
        safe: "No"
        unsafe: "Yes"
```

### Disabling a Bundled Adapter

To disable a bundled adapter entirely and use default PALACE behavior, add the matching pattern with an empty body:

```yaml
# ~/.config/palace/io_adapters.yaml

"granite-guardian-*":  # disables bundled adapter — uses default PALACE prompts
```

An empty entry produces a passthrough adapter: the model receives the standard task prompt and its raw output is used as-is.

### Schema

```yaml
"model-name-or-glob":
  input:                    # optional — omit to use default prompt
    template: "string"      # template with placeholders
  output:                   # optional — omit for passthrough
    pattern: "regex"        # regex with named capture groups
    template: "string"      # output format with group placeholders
    mapping:                # optional — per-group value translation
      groupname:
        captured: "output"
```

## Input Adapter

The input adapter controls what prompt the model receives. When defined, it replaces the task type's formatted prompt entirely.

### Available Placeholders

| Placeholder | Source | Description |
|-------------|--------|-------------|
| `{objective}` | `task.objective` | The task question or text. Always available. |
| `{document}` | `task.document` | Reference document, if present. Empty string if absent. |
| `{attachment}` | Loaded file content | Text attachment content, if present. Empty string if absent. |
| `{expected}` | `task.expected` | Expected answer, if present. Rarely needed in input. |

Missing or empty fields are substituted with an empty string — no errors.

### Examples

Send only the raw objective (most common for guardrails):

```yaml
input:
  template: "{objective}"
```

Add a prefix and suffix:

```yaml
input:
  template: "Classify the following text:\n{objective}\n\nAnswer:"
```

Include document context:

```yaml
input:
  template: |
    Document:
    {document}

    Question: {objective}
```

Include attachment content:

```yaml
input:
  template: |
    {attachment}

    {objective}
```

The YAML `|` syntax preserves newlines, which is useful for multi-line templates.

## Output Adapter

The output adapter parses the model's raw output and reformats it into what the task type's verification logic expects.

### Pattern

A Python regex with **named capture groups** using `(?P<name>...)` syntax:

```yaml
output:
  pattern: "(?P<result>safe|unsafe)"
```

This captures the value `safe` or `unsafe` into a group named `result`.

For multiple values:

```yaml
output:
  pattern: |
    User safety: (?P<safety>\w+)
    Category: (?P<category>\w+)
```

### Template

Defines how captured groups are assembled into the final output. Uses `{groupname}` placeholders:

```yaml
output:
  template: "<Unsafe>{result}</Unsafe>"
```

If `template` is omitted, the first capture group's value is used as-is.

### Mapping

Translates captured values before they're placed in the template. Defined per group:

```yaml
output:
  mapping:
    result:
      safe: "No"
      unsafe: "Yes"
```

With this mapping, if the pattern captures `result = "unsafe"`, it becomes `"Yes"` before template substitution.

If a captured value is not found in the mapping, it passes through unchanged and PALACE logs a warning. If no mapping is defined for a group, values pass through unchanged.

## Complete Examples

### Single-Label Guardrail (LlamaGuard)

Model outputs: `"unsafe"` or `"safe"`

```yaml
"llamaguard-*":
  input:
    template: "{objective}"
  output:
    pattern: "(?P<result>safe|unsafe)"
    template: "<Unsafe>{result}</Unsafe>"
    mapping:
      result:
        safe: "No"
        unsafe: "Yes"
```

Flow: `"unsafe"` → captures `result="unsafe"` → maps to `"Yes"` → produces `<Unsafe>Yes</Unsafe>`

### Multi-Label Guardrail

Model outputs:
```
Safety: unsafe
Category: violence
```

```yaml
"multi-guard-*":
  input:
    template: "{objective}"
  output:
    pattern: |
      Safety: (?P<safety>\w+)
      Category: (?P<category>\w+)
    template: |
      <Unsafe>{safety}</Unsafe>
      <Category>{category}</Category>
    mapping:
      safety:
        safe: "No"
        unsafe: "Yes"
```

### QA Model with Fixed Output Format

Model outputs: `"The answer is: Paris"`

```yaml
"my-qa-model":
  input:
    template: "{objective}"
  output:
    pattern: "(?:The answer is: )?(?P<answer>.+)"
    template: "{answer}"
```

Flow: `"The answer is: Paris"` → captures `answer="Paris"` → produces `"Paris"` → QA judge compares to reference.

### Model Needing Custom Prompt Format

Model expects a specific chat format but can follow output instructions:

```yaml
"custom-format-model":
  input:
    template: "[INST] {objective} [/INST]"
```

No output adapter needed — the model follows PALACE's output format.

## Glob Pattern Matching

Model names are matched against adapter keys using glob patterns (Python's `fnmatch`):

| Pattern | Matches | Doesn't Match |
|---------|---------|---------------|
| `llamaguard-*` | `llamaguard-7b`, `llamaguard-3-8b` | `LlamaGuard-7b` (case-sensitive) |
| `meta-llama/LlamaGuard-*` | `meta-llama/LlamaGuard-7b` | `llamaguard-7b` |
| `*guard*` | `llamaguard-7b`, `wildguard-7b` | `gpt-4o` |
| `my-model` | `my-model` (exact match) | `my-model-v2` |

Patterns are **case-sensitive** on Linux. The first matching pattern in the file is used.

## Priority Order

PALACE resolves adapters in this order:

1. **Programmatic adapter** — passed directly to `evaluate(io_adapter={...})`. Used by palace-gradin.
2. **User file adapter** — first glob match in `~/.config/palace/io_adapters.yaml`. Used by CLI users.
3. **Bundled adapter** — first glob match in the package's `bundled_io_adapters.yaml`. Ships with PALACE.
4. **No adapter** — default PALACE behavior.

The first match wins. If your user file has a pattern that matches the model, bundled adapters are never checked. The evaluation log shows which source was used:

```
🔧 Using I/O adapter for granite-guardian-3.1-8b (bundled)
🔧 Using I/O adapter for nemotron_moderator (user)
🔧 Using I/O adapter for custom-model (explicit)
```

## Gradin Usage

In palace-gradin's web UI, adapters are configured per-model:

1. Add an endpoint and pair API models with tasklists
2. Click the 🔧 wrench button on a model card (turns orange when an adapter is configured)
3. Fill in the adapter fields (same schema as the YAML file)
4. Save the adapter

Each model can have its own adapter. Endpoints with adapters show an **N Adapter(s)** badge.

## Troubleshooting

### "My adapter isn't being applied"

- Check that the model name matches the glob pattern exactly (case-sensitive)
- Run with `--limit 1` and look for the `🔧 Using I/O adapter for <model>` message in the output
- Verify the YAML file is at `~/.config/palace/io_adapters.yaml`

### "Output pattern doesn't match"

- Look for the yellow warning: *"Adapter output pattern did not match"*
- Test your regex against the model's actual output (run with `--limit 1` first)
- Remember that `.` doesn't match newlines by default — use `[\s\S]` or `(?s)` flag for multi-line matching

### "Getting 0% accuracy with adapter"

- Verify the output template produces the format the task type expects
- For Classification: output must be `<LabelName>value</LabelName>` where `value` matches one of the class names
- For QA: output is free text compared by an LLM judge — usually no output adapter needed
- Check that mapping values match the expected class names exactly

### Testing an adapter

Run a single task first to verify:

```bash
palace run llamaguard-7b -m GuardBench-EN -l 1
```

Check the output for:
- `🔧 Using I/O adapter for llamaguard-7b` — adapter was found
- The task prompt shown should be the adapted input (e.g., just the raw text)
- The agent answer should show the adapted output (e.g., `<Unsafe>Yes</Unsafe>`)

---

## Related Pages

- [Run Evaluations](run-evaluations.md) — Running evaluations with CLI and API
- [Custom Criteria](custom-criteria.md) — Configuring task type verification
- [Debug Evaluations](debug-evaluations.md) — Troubleshooting evaluation issues
