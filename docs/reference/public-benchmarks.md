# Public Benchmarks

PALACE supports automatic downloading and conversion of public HuggingFace benchmarks into the PALACE tasklist format.

## Supported Benchmarks

The following public benchmarks can be downloaded with `palace-download`:

| Benchmark | HuggingFace ID | Category | Task Type | Modality |
|-----------|----------------|----------|-----------|----------|
| BABILong-32k | `RMT-team/babilong` | Long Context | QA | Text |
| BABILong-128k | `RMT-team/babilong` | Long Context | QA | Text |
| CURIE-protein | `nhop/curie` | Expert Reasoning | QA | Text |
| HotpotQA | `hotpotqa/hotpot_qa` | Agentic | QA | Text |
| GAIA | `gaia-benchmark/GAIA` | Agentic | QA | Text+Files |
| SimpleQA | `basicv8vc/SimpleQA` | General Knowledge | QA | Text |
| SimpleQA-Verified | `google/simpleqa-verified` | General Knowledge | QA | Text |
| AssistantBench | `AssistantBench/AssistantBench` | Agentic | QA | Text |
| Humanity's Last Exam | `cais/hle` | Expert Reasoning | QA | Text+Image |
| VLSBench | `Foreshhh/vlsbench` | Safety | Classification | Text+Image |
| MMLU-Pro | `TIGER-Lab/MMLU-Pro` | General Knowledge | Classification | Text |
| MMLU | `cais/mmlu` | General Knowledge | Classification | Text |
| SuperGPQA | `m-a-p/SuperGPQA` | Expert Reasoning | Classification | Text |
| MMMLU | `openai/MMMLU` | General Knowledge | Classification | Text |
| Belebele | `facebook/belebele` | Multilingual | Classification | Text |
| HellaSwag | `Rowan/hellaswag` | Common Sense Reasoning | Classification | Text |
| MUSR | `edinburgh-dawg/labelchaos` | General Reasoning | Classification | Text |
| MATH-500 | `HuggingFaceH4/MATH-500` | Mathematical Reasoning | QA | Text |
| AIME 2025 | `AI-MO/aimo-validation-aime` | Mathematical Reasoning | QA | Text |
| MGSM | `juletxara/mgsm` | Multilingual Reasoning | QA | Text |
| BBH | `lukaemon/bbh` | General Reasoning | QA | Text |
| GPQA Diamond | `Idavidrein/gpqa` | Expert Reasoning | Classification | Text |
| MMMU | `MMMU/MMMU` | Visual Reasoning | Classification | Text+Image |
| MMMU Pro | `MMMU/MMMU_Pro` | Visual Reasoning | Classification | Text+Image |
| IFEval | `google/IFEval` | Instruction Following | Instruction Following | Text |

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
palace-download -t SimpleQA HotpotQA IFEval
```

Skip already downloaded benchmarks:

```bash
palace-download --skip-existing
```

## Benchmark Details

### QA Benchmarks

#### BABILong (32k / 128k)

Long-context reasoning benchmark with 5 question types (qa1-qa5). Tests ability to find relevant information in long documents.

- **Source**: [RMT-team/babilong](https://huggingface.co/datasets/RMT-team/babilong)
- **Attachments**: Inline text documents (32k or 128k tokens)
- **Verification**: LLM judge (semantic equivalence)

#### CURIE-protein

Expert-level protein structure reasoning. Requires domain knowledge to answer questions about protein sequences.

- **Source**: [nhop/curie](https://huggingface.co/datasets/nhop/curie)
- **Attachments**: Inline protein data files
- **Verification**: Custom verificator (exact JSON match)

#### HotpotQA

Multi-hop question answering requiring reasoning across multiple documents.

- **Source**: [hotpotqa/hotpot_qa](https://huggingface.co/datasets/hotpotqa/hotpot_qa)
- **Difficulty levels**: easy, medium, hard
- **Verification**: LLM judge (semantic equivalence)

#### GAIA

General AI Assistant benchmark testing real-world task completion with file attachments.

- **Source**: [gaia-benchmark/GAIA](https://huggingface.co/datasets/gaia-benchmark/GAIA)
- **Attachments**: External files (PDFs, images, spreadsheets)
- **Difficulty levels**: 1, 2, 3
- **Verification**: LLM judge (semantic equivalence)

#### SimpleQA

Factual question answering benchmark from OpenAI testing general knowledge.

- **Source**: [basicv8vc/SimpleQA](https://huggingface.co/datasets/basicv8vc/SimpleQA)
- **Verification**: LLM judge (semantic equivalence)

#### SimpleQA-Verified

Improved factuality benchmark from Google DeepMind (1,000 questions). Builds on SimpleQA with corrected labels, reduced topical bias, and removed redundancy.

- **Source**: [google/simpleqa-verified](https://huggingface.co/datasets/google/simpleqa-verified)
- **Verification**: LLM judge (semantic equivalence)

#### AssistantBench

Web-based task completion benchmark requiring information retrieval and synthesis.

- **Source**: [AssistantBench/AssistantBench](https://huggingface.co/datasets/AssistantBench/AssistantBench)
- **Difficulty levels**: easy, hard
- **Verification**: LLM judge (semantic equivalence)

#### Humanity's Last Exam

Expert-level multimodal questions across diverse academic domains.

- **Source**: [cais/hle](https://huggingface.co/datasets/cais/hle)
- **Attachments**: Inline images (base64)
- **Verification**: LLM judge (semantic equivalence)
- **Requirements**: Vision-capable model

#### MATH-500

500 competition mathematics problems covering algebra, geometry, combinatorics, and number theory.

- **Source**: [HuggingFaceH4/MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500)
- **Verification**: Custom verificator (numeric comparison)

#### AIME 2025

American Invitational Mathematics Examination problems (2025 edition).

- **Source**: [AI-MO/aimo-validation-aime](https://huggingface.co/datasets/AI-MO/aimo-validation-aime)
- **Verification**: Custom verificator (numeric comparison)

#### MGSM

Multilingual Grade School Math — arithmetic word problems in 10 languages.

- **Source**: [juletxara/mgsm](https://huggingface.co/datasets/juletxara/mgsm)
- **Verification**: Custom verificator (numeric comparison)

#### BBH

BIG-Bench Hard — 27 challenging subtasks from the BIG-Bench suite requiring multi-step reasoning.

- **Source**: [lukaemon/bbh](https://huggingface.co/datasets/lukaemon/bbh)
- **Configs**: 27 subtasks (boolean_expressions, causal_judgement, etc.)
- **Verification**: LLM judge (semantic equivalence)

### Classification Benchmarks

#### MMLU-Pro

Massive Multitask Language Understanding (Pro edition) with 10-choice questions across 14 disciplines.

- **Source**: [TIGER-Lab/MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro)
- **Verification**: Exact match (Classification with dynamic classes)

#### MMLU

Original Massive Multitask Language Understanding — 57 subjects, 4-choice questions.

- **Source**: [cais/mmlu](https://huggingface.co/datasets/cais/mmlu)
- **Configs**: 57 subjects
- **Verification**: Exact match (Classification with dynamic classes)

#### SuperGPQA

Graduate-level domain expertise across 285 academic disciplines.

- **Source**: [m-a-p/SuperGPQA](https://huggingface.co/datasets/m-a-p/SuperGPQA)
- **Verification**: Exact match (Classification with dynamic classes)

#### MMMLU

Multilingual MMLU — multiple-choice questions across languages.

- **Source**: [openai/MMMLU](https://huggingface.co/datasets/openai/MMMLU)
- **Verification**: Exact match (Classification with dynamic classes)

#### Belebele

Reading comprehension in 122 languages — 4-choice multiple-choice questions.

- **Source**: [facebook/belebele](https://huggingface.co/datasets/facebook/belebele)
- **Verification**: Exact match (Classification with dynamic classes)

#### HellaSwag

Commonsense natural language inference — 4-choice sentence completion.

- **Source**: [Rowan/hellaswag](https://huggingface.co/datasets/Rowan/hellaswag)
- **Split**: validation (test split has no labels)
- **Verification**: Exact match (Classification with dynamic classes)

#### MUSR

Multi-step reasoning with uncertainty — complex reasoning scenarios.

- **Source**: [edinburgh-dawg/labelchaos](https://huggingface.co/datasets/edinburgh-dawg/labelchaos)
- **Config**: clean
- **Verification**: Exact match (Classification with dynamic classes)

#### GPQA Diamond

Graduate-level science questions (198 tasks). Requires expert knowledge in physics, chemistry, and biology.

- **Source**: [Idavidrein/gpqa](https://huggingface.co/datasets/Idavidrein/gpqa)
- **Config**: gpqa_diamond
- **Access**: Gated — requires HuggingFace token
- **Verification**: Exact match (Classification with shuffled 4-choice answers)

#### MMMU

Multimodal multi-discipline understanding — 900 tasks across 30 academic subjects with images.

- **Source**: [MMMU/MMMU](https://huggingface.co/datasets/MMMU/MMMU)
- **Configs**: 30 subjects (Accounting, Agriculture, Architecture, etc.)
- **Split**: validation
- **Attachments**: Up to 7 images per task (multi-image)
- **Verification**: Exact match (Classification with dynamic classes)
- **Requirements**: Vision-capable model

#### MMMU Pro

Harder version of MMMU with more answer options.

- **Source**: [MMMU/MMMU_Pro](https://huggingface.co/datasets/MMMU/MMMU_Pro)
- **Config**: standard (4 options)
- **Split**: test
- **Attachments**: Up to 7 images per task (multi-image)
- **Verification**: Exact match (Classification with dynamic classes)
- **Requirements**: Vision-capable model

#### VLSBench

Multimodal safety benchmark for guardrail models. All samples are adversarial (unsafe). Each task combines a text prompt with an image that together form potentially unsafe content.

- **Source**: [Foreshhh/vlsbench](https://huggingface.co/datasets/Foreshhh/vlsbench)
- **Attachments**: PNG images (auto-resized to max 1024px)
- **Verification**: Exact match (Classification)
- **Labels**: `Unsafe: Yes/No`
- **Requirements**: Vision-capable model

### Instruction Following Benchmarks

#### IFEval

Instruction-Following Evaluation benchmark — 541 tasks with 25 types of syntactic constraints (word count, format, keywords, case, etc.). Verification is fully deterministic.

- **Source**: [google/IFEval](https://huggingface.co/datasets/google/IFEval)
- **Verification**: Deterministic constraint checkers (no LLM judge)
- **Metrics**: Constraint satisfaction score + accuracy

---

## Related Pages

- [Add Public Benchmark](../howto/add-public-benchmark.md) — How to add new benchmarks
- [Official Tasklists](tasklists/index.md) — JRC-developed benchmarks
- [CLI Reference](cli.md) — Command-line documentation
- [Evaluation Pipeline](../concepts/evaluation-pipeline.md) — Multimodal support details
