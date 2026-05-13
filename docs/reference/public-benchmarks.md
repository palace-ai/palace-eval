# Public Benchmarks

PALACE supports automatic downloading and conversion of public HuggingFace benchmarks into the PALACE tasklist format.

## Supported Benchmarks

The following public benchmarks can be downloaded with `palace-download`:

| Benchmark | HuggingFace ID | Category | Task Type | Modality | Splits |
|-----------|----------------|----------|-----------|----------|--------|
| BABILong-32k | `RMT-team/babilong` | Long Context | QA | Text | qa1-qa5 |
| BABILong-128k | `RMT-team/babilong` | Long Context | QA | Text | qa1-qa5 |
| CURIE-protein | `nhop/curie` | Expert Reasoning | QA | Text | train |
| HotpotQA | `hotpotqa/hotpot_qa` | Agentic | QA | Text | validation |
| GAIA | `gaia-benchmark/GAIA` | Agentic | QA | Text+Files | validation |
| SimpleQA | `basicv8vc/SimpleQA` | General Knowledge | QA | Text | test |
| SimpleQA-Verified | `google/simpleqa-verified` | General Knowledge | QA | Text | eval |
| AssistantBench | `AssistantBench/AssistantBench` | Agentic | QA | Text | validation |
| Humanity's Last Exam | `cais/hle` | Expert Reasoning | QA | Text+Image | test |
| VLSBench | `Foreshhh/vlsbench` | Safety | Classification | Text+Image | train |

**Modality legend:**
- **Text**: Text-only tasks
- **Text+Image**: Multimodal tasks with image attachments (requires vision model)
- **Text+Files**: Tasks with file attachments (PDFs, spreadsheets, etc.)

## Downloading Benchmarks

Download all public benchmarks:

```bash
palace-download
```

Download specific benchmarks:

```bash
palace-download -t SimpleQA HotpotQA
```

Skip already downloaded benchmarks:

```bash
palace-download --skip-existing
```

## Benchmark Details

### BABILong (32k / 128k)

Long-context reasoning benchmark with 5 question types (qa1-qa5). Tests ability to find relevant information in long documents.

- **Source**: [RMT-team/babilong](https://huggingface.co/datasets/RMT-team/babilong)
- **Attachments**: Inline text documents (32k or 128k tokens)
- **Verification**: LLM judge (semantic equivalence)

### CURIE-protein

Expert-level protein structure reasoning. Requires domain knowledge to answer questions about protein sequences.

- **Source**: [nhop/curie](https://huggingface.co/datasets/nhop/curie)
- **Attachments**: Inline protein data files
- **Verification**: Custom verificator (exact JSON match)

### HotpotQA

Multi-hop question answering requiring reasoning across multiple documents.

- **Source**: [hotpotqa/hotpot_qa](https://huggingface.co/datasets/hotpotqa/hotpot_qa)
- **Difficulty levels**: easy, medium, hard
- **Verification**: LLM judge (semantic equivalence)

### GAIA

General AI Assistant benchmark testing real-world task completion with file attachments.

- **Source**: [gaia-benchmark/GAIA](https://huggingface.co/datasets/gaia-benchmark/GAIA)
- **Attachments**: External files (PDFs, images, spreadsheets)
- **Difficulty levels**: 1, 2, 3
- **Verification**: LLM judge (semantic equivalence)

### SimpleQA

Factual question answering benchmark from OpenAI testing general knowledge.

- **Source**: [basicv8vc/SimpleQA](https://huggingface.co/datasets/basicv8vc/SimpleQA)
- **Verification**: LLM judge (semantic equivalence)

### SimpleQA-Verified

Improved factuality benchmark from Google DeepMind (1,000 questions). Builds on SimpleQA with corrected labels, reduced topical bias, and removed redundancy.

- **Source**: [google/simpleqa-verified](https://huggingface.co/datasets/google/simpleqa-verified)
- **Verification**: LLM judge (semantic equivalence)

### AssistantBench

Web-based task completion benchmark requiring information retrieval and synthesis.

- **Source**: [AssistantBench/AssistantBench](https://huggingface.co/datasets/AssistantBench/AssistantBench)
- **Difficulty levels**: easy, hard
- **Verification**: LLM judge (semantic equivalence)

### Humanity's Last Exam

Expert-level multimodal questions across diverse academic domains.

- **Source**: [cais/hle](https://huggingface.co/datasets/cais/hle)
- **Attachments**: Inline images (base64)
- **Verification**: LLM judge (semantic equivalence)
- **Requirements**: Vision-capable model (e.g., GPT-4o)

### VLSBench

Multimodal safety benchmark for guardrail models. All samples are adversarial (unsafe). Each task combines a text prompt with an image that together form potentially unsafe content.

- **Source**: [Foreshhh/vlsbench](https://huggingface.co/datasets/Foreshhh/vlsbench)
- **Attachments**: PNG images (auto-resized to max 1024px)
- **Verification**: Exact match (Classification)
- **Labels**: `Unsafe: Yes/No`
- **Requirements**: Vision-capable model (e.g., GPT-4o)

---

## Related Pages

- [Add Public Benchmark](../howto/add-public-benchmark.md) — How to add new benchmarks
- [Official Tasklists](tasklists/index.md) — JRC-developed benchmarks
- [CLI Reference](cli.md) — Command-line documentation
- [Evaluation Pipeline](../concepts/evaluation-pipeline.md) — Multimodal support details
