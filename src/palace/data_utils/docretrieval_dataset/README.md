# DocRetrieval Dataset Generator

Generates QA benchmark datasets that evaluate an AI agent's ability to retrieve and synthesize information from multiple documents. Questions are designed to be **unanswerable without access to all required source files**.

## Purpose

Standard QA benchmarks often test knowledge that LLMs already have in their training data. This dataset specifically tests:
- Document retrieval capability (agent must find the right files)
- Multi-document reasoning (answer requires synthesizing info across files)
- Resistance to hallucination (can't guess without the actual content)

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATASET GENERATION PIPELINE                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. FILE COMBINATIONS                                                   │
│     ┌───────┐ ┌───────┐ ┌───────┐                                       │
│     │ A.pdf │ │ B.pdf │ │ C.pdf │ → [A,B,C], [A,B], [A,C], [B,C], ...   │
│     └───────┘ └───────┘ └───────┘                                       │
│                                                                         │
│  2. TOPIC DISCOVERY (per combination)                                   │
│     LLM reads all files → finds specific common topics                  │
│     "Both documents discuss labeling requirements for alcohol products" │
│                                                                         │
│  3. BATCH QUESTION GENERATION (per topic)                               │
│     LLM generates N diverse questions requiring ALL files               │
│     + expected answers + references                                     │
│                                                                         │
│  4. QUESTION IMPROVEMENT                                                │
│     Remove vague phrases like "according to the documents"              │
│     Keep specific references like "according to the AI Act"             │
│                                                                         │
│  5. VALIDATION (the key quality gate)                                   │
│     For each file in the combination:                                   │
│       - Give tester LLM access to all OTHER files (N-1)                 │
│       - Ask it to answer the question                                   │
│       - Judge LLM evaluates if answer is correct                        │
│     Question passes ONLY if tester fails for EVERY file removal         │
│     → Guarantees every file is necessary to answer                      │
│                                                                         │
│  6. OUTPUT                                                              │
│     tasks.json + copied PDFs → ready for evaluation                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Usage

```bash
# From palace-lib root, with venv activated
python -m palace.data_utils.docretrieval_dataset.create_dataset <fileset>

# Options
python -m palace.data_utils.docretrieval_dataset.create_dataset pubsy-alcohol \
    --max-topics 5 \           # Max topics per file combination (default: 5)
    -n 6 \                     # Tasks per topic (default: 6)
    --confidence 3             # Validation attempts per file removal (default: 3)
```

## Output Format

Generated dataset is saved to `~/.cache/palace/tasklists/DocRetrieval-<fileset>/`:

```
DocRetrieval-<fileset>/
├── info.json                  # Dataset metadata
├── tasks.json                 # Generated tasks
└── task_files/                # Copied source PDFs
```

### Task Schema

```json
{
    "id": "DocRetrieval-pubsy-alcohol_file1_file2_0_1",
    "objective": "What labeling requirements for alcohol...",
    "expected": "The expected answer text...",
    "references": "Verbatim quotes from source documents...",
    "difficulty": 2,
    "documents": ["file1.pdf", "file2.pdf"],
    "topic": "The common topic this question is based on",
    "attachment": "",
    "custom_verificator": ""
}
```

- `difficulty`: Number of files required (1, 2, or 3)
- `documents`: List of files needed to answer
- `references`: LLM-generated quotes (not verified for exact match)

## Adding New Document Sets

1. Create a folder under `files/` with your PDFs:
   ```
   files/my-new-topic/
   ├── document1.pdf
   ├── document2.pdf
   └── document3.pdf
   ```

2. Run the generator:
   ```bash
   python -m palace.data_utils.docretrieval_dataset.create_dataset my-new-topic
   ```
