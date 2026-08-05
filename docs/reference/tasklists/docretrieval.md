# DocRetrieval

DocRetrieval is an agentic QA benchmark that evaluates a model's ability to retrieve and synthesize information from multiple documents. Unlike standard QA benchmarks that test knowledge already in the model's training data, DocRetrieval specifically tests document retrieval capability—questions are designed to be unanswerable without access to the actual source files.

## Overview

| Property | Value |
|----------|-------|
| **Task Type** | QA |
| **Category** | Agentic |
| **Document Sets** | 2 (AI regulations, EU legal corpus) |
| **Total Tasks** | 1,420 |
| **Requires** | Tool access (document retrieval) |

## Purpose and Motivation

Standard QA benchmarks often test knowledge that LLMs already have in their training data, making it difficult to distinguish between genuine retrieval capability and memorization. DocRetrieval addresses this by:

- **Requiring actual retrieval**: Questions cannot be answered from training data alone
- **Testing multi-document reasoning**: Answers require synthesizing information across multiple files
- **Resistance to hallucination**: Models cannot guess without the actual content
- **Using real documents**: Based on actual EU legal and policy documents

This makes DocRetrieval particularly valuable for evaluating RAG (Retrieval-Augmented Generation) systems and agentic document search capabilities.

## Available Variants

| Variant | Document Set | HuggingFace ID | Tasks |
|---------|--------------|----------------|------:|
| DocRetrieval-ai | AI Act & related regulations | `jrc-ai/DocRetrieval-ai` | 189 |
| DocRetrieval-pubsy-recsys-dsa | EU Publications Office, recommendation systems, DSA | `jrc-ai/DocRetrieval-pubsy-recsys-dsa` | 1,231 |

### DocRetrieval-ai

Focuses on EU AI regulations, including:
- **Guidelines for GPAI Models** — Technical guidelines for general-purpose AI
- **AI Continent Action Plan** — EU strategy for AI development
- **AI in Science Strategy** — Application of AI in scientific research

### DocRetrieval-pubsy-recsys-dsa

Covers a broader range of EU legal documents related to:
- Publications Office regulations
- Recommendation system requirements
- Digital Services Act provisions

## Data Composition

### Task Structure

Each task includes:

- **objective**: The question to answer
- **expected**: The correct answer
- **references**: Verbatim quotes from source documents supporting the answer
- **documents**: List of PDF files required to answer the question
- **topic**: The common topic the question is based on
- **difficulty**: Number of documents required (1, 2, or 3)

```json
{
    "id": "DocRetrieval-ai_Guidelines_GPAI_Models_AI_Continent_Action_Plan_AI_in_Science_Strategy_0_1",
    "objective": "What three specific actions must a provider carry out to estimate and secure the training compute (in FLOP) required for a general-purpose AI model, and which EU document supports each of these actions?",
    "expected": "1. **Check the model against the EU's training-compute threshold** – the model must have a training compute greater than 10^23 FLOP to be regarded as a general-purpose AI model.\n2. **Estimate the training compute before the large pre-training run** – the provider must calculate the expected cumulative compute prior to starting training.\n3. **Secure the required compute through the EU's AI-Factories/Gigafactories infrastructure** – the estimated compute is used to obtain dedicated access to AI-Factories.",
    "references": "- **Guidelines GPAI Models** – Paragraph 17 states the indicative criterion...\n- **AI Continent Action Plan** – Paragraph 31-32 explains that providers must...\n- **AI in Science Strategy** – Section 3.2 (Compute) notes that...",
    "documents": ["Guidelines GPAI Models.pdf", "AI Continent Action Plan.pdf", "AI in Science Strategy.pdf"],
    "topic": "Standardised estimation and monitoring of training compute (FLOP) for AI models.",
    "difficulty": "DocRetrieval-ai_DocRetrieval-ai_30"
}
```

### Question Characteristics

Questions are specifically designed to:

1. **Require multiple documents**: The answer cannot be found in any single document
2. **Test synthesis**: Information must be combined across sources
3. **Include specific references**: Questions often ask for document citations
4. **Avoid vague phrasing**: Questions are concrete and specific

## Configuration

```json
{
    "name": "DocRetrieval-ai",
    "id": "jrc-ai/DocRetrieval-ai",
    "version": "1.0.0",
    "original": true,
    "category": "Agentic",
    "task_type": "QA"
}
```

## Evaluation Methodology

DocRetrieval uses LLM-based semantic evaluation:

1. **Agent execution**: The model (with tool access) attempts to answer the question
2. **Document retrieval**: The agent must find and read the relevant documents
3. **Answer generation**: The agent synthesizes an answer from retrieved content
4. **LLM judge evaluation**: A judge model compares the answer against the expected answer using semantic equivalence

### Requirements

DocRetrieval tasks require agentic evaluation (`--agentic`) with:
- **Document fetch tool**: Ability to retrieve and read PDF documents
- **Web search tool** (optional): May help locate documents
- **Sufficient context**: Documents can be lengthy

## Dataset Construction

The DocRetrieval dataset is constructed through a sophisticated multi-stage pipeline designed to ensure question quality:

### Pipeline Overview

```
1. FILE COMBINATIONS
   [A.pdf, B.pdf, C.pdf] → [A,B,C], [A,B], [A,C], [B,C], ...

2. TOPIC DISCOVERY (per combination)
   LLM reads all files → finds specific common topics
   "Both documents discuss labeling requirements for alcohol products"

3. BATCH QUESTION GENERATION (per topic)
   LLM generates N diverse questions requiring ALL files
   + expected answers + references

4. QUESTION IMPROVEMENT
   Remove vague phrases like "according to the documents"
   Keep specific references like "according to the AI Act"

5. VALIDATION (the key quality gate)
   For each file in the combination:
     - Give tester LLM access to all OTHER files (N-1)
     - Ask it to answer the question
     - Judge LLM evaluates if answer is correct
   Question passes ONLY if tester fails for EVERY file removal
   → Guarantees every file is necessary to answer

6. OUTPUT
   tasks.json + copied PDFs → ready for evaluation
```

### Validation Process

The validation step is crucial for ensuring question quality. For each question:

1. **File removal test**: For each required document, test whether the question can be answered without it
2. **Multiple attempts**: Each removal is tested multiple times (configurable confidence level)
3. **Strict passing**: A question only passes if it fails for every single file removal

This ensures that every document listed in the `documents` field is genuinely necessary to answer the question.

## Running Evaluations

```bash
# Download the tasklist
palace download DocRetrieval-ai

# Run evaluation
palace run DocRetrieval-ai -m gpt-4o -l 20
```

## Interpreting Results

### Metrics

- **Accuracy**: Percentage of questions answered correctly
- **Per-difficulty breakdown**: Performance by number of required documents
- **Retrieval success rate**: How often the agent found the right documents

### What to Look For

- **Multi-document performance**: Does accuracy drop as more documents are required?
- **Retrieval patterns**: Is the agent finding the right documents?
- **Synthesis quality**: Are answers properly combining information?

## Use Cases

- **RAG system evaluation**: Testing retrieval-augmented generation pipelines
- **Agent capability assessment**: Evaluating document search and synthesis
- **Legal/policy AI**: Testing systems designed for regulatory document analysis
- **Enterprise search**: Benchmarking internal document retrieval systems

## Limitations

- **Document availability**: Requires access to the source PDF documents
- **EU-specific content**: Documents are EU regulations and policies
- **English-focused**: Questions and documents are primarily in English
- **Static corpus**: Document set is fixed at dataset creation time

---

## Related Pages

- [QA Task Type](../../task-types/qa.md) — How QA evaluation works
- [Run Evaluations Guide](../../howto/run-evaluations.md) — Running agentic evaluations
- [Official Tasklists Overview](index.md) — All official PALACE tasklists
