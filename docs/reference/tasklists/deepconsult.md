# DeepConsult

DeepConsult is a report generation benchmark that evaluates a model's ability to produce comprehensive, well-researched consulting reports on complex business and policy topics. The benchmark tests long-form generation capabilities using real consulting queries and high-quality reference reports.

## Overview

| Property | Value |
|----------|-------|
| **Task Type** | Criteria Evaluation |
| **Category** | Criteria Evaluation |
| **Total Tasks** | 102 |
| **Reference Source** | OpenAI Deep Research |
| **Report Length** | 2,000–15,000+ words |

## Purpose and Motivation

Long-form content generation is increasingly important for enterprise applications, from market research to policy analysis. DeepConsult addresses the need for rigorous evaluation of these capabilities by:

- **Testing comprehensive analysis**: Reports must cover multiple aspects of complex topics
- **Requiring structured output**: Reports should have clear organization and logical flow
- **Evaluating research depth**: Answers should demonstrate thorough understanding
- **Using real-world queries**: Topics reflect actual consulting and research needs

The benchmark is particularly valuable for evaluating models intended for research assistance, business intelligence, and policy analysis applications.

## Data Composition

### Query Topics

DeepConsult covers a diverse range of business and policy topics, including:

- **Investment analysis**: Evaluating investment strategies and market opportunities
- **Technology trends**: Analyzing emerging technologies and their implications
- **Policy evaluation**: Assessing regulatory frameworks and policy impacts
- **Market sizing**: Estimating market potential and growth trajectories
- **Risk assessment**: Identifying and analyzing business and strategic risks
- **Competitive analysis**: Examining industry dynamics and competitive landscapes

### Task Structure

Each task consists of a consulting query and a comprehensive reference report:

```json
{
    "id": "DeepConsult-0",
    "objective": "Evaluate the potential consequences of TikTok bans on investment risks and analyze how companies can strategically navigate these challenges. Consider how varying degrees of restrictions might impact business operations and explore adaptive measures to mitigate associated risks.",
    "expected": "# TikTok Bans and Investment Risk Analysis\n\n## Executive Summary\n...\n\n## Market Impact Assessment\n...\n\n## Strategic Recommendations\n..."
}
```

### Reference Reports

The reference reports in DeepConsult are generated using OpenAI's Deep Research capability, providing high-quality baselines that demonstrate:

- **Comprehensive coverage**: Multiple sections addressing different aspects
- **Structured presentation**: Clear headings, subheadings, and organization
- **Evidence-based analysis**: Citations and references to support claims
- **Actionable insights**: Practical recommendations and conclusions

Reference reports typically range from 2,000 to 15,000+ words, depending on topic complexity.

## Configuration

```json
{
    "name": "DeepConsult",
    "id": "jrc-ai/DeepConsult",
    "version": "1.0.0",
    "original": true,
    "category": "Criteria Evaluation",
    "task_type": "Criteria Evaluation"
}
```

## Evaluation Methodology

DeepConsult uses LLM-based pairwise comparison:

1. **Report generation**: The model generates a comprehensive report for the query
2. **Pairwise comparison**: An LLM judge compares the generated report against the reference
3. **Criteria evaluation**: The judge assesses multiple quality dimensions
4. **Score aggregation**: Individual criteria scores are combined into an overall score

### Default Evaluation Criteria

When no custom criteria are specified, Criteria Evaluation tasks use default criteria covering:

- **Content quality**: Accuracy, depth, and relevance of information
- **Structure and organization**: Logical flow and clear presentation
- **Completeness**: Coverage of key aspects of the topic
- **Writing quality**: Clarity, professionalism, and readability

### Scoring

The pairwise comparison produces:
- **Winner determination**: Which report is better overall
- **Per-criterion scores**: Ratings for each evaluation dimension
- **Normalized score**: A 0-1 score based on the gap between reports

## Dataset Construction

The DeepConsult dataset is constructed from real consulting queries:

1. **Query collection**: Consulting-style questions are collected covering diverse business and policy topics
2. **Reference generation**: Each query is processed through OpenAI's Deep Research to generate comprehensive reference reports
3. **Quality review**: Reports are reviewed for completeness and quality
4. **Format conversion**: Data is converted to the PALACE task format

The use of Deep Research for reference generation ensures high-quality baselines that represent the current state-of-the-art in AI-assisted research.

## Running Evaluations

```bash
# Download the tasklist
palace download DeepConsult

# Run evaluation (note: generates long reports, may be slow)
palace run DeepConsult -m gpt-4o -l 10

# Run with specific model
palace run DeepConsult -m gpt-4o -l 5
```

### Considerations

- **Generation time**: Long reports take significant time to generate
- **Token usage**: Both generation and evaluation consume substantial tokens
- **Judge model**: Evaluation quality depends on the judge model's capabilities

## Interpreting Results

### Metrics

- **Win rate**: Percentage of reports judged better than or equal to reference
- **Average score**: Mean normalized score across all tasks
- **Per-criterion breakdown**: Performance on individual quality dimensions

### What to Look For

- **Consistency**: Does the model maintain quality across different topics?
- **Structure**: Are reports well-organized with clear sections?
- **Depth vs. breadth**: Does the model balance comprehensive coverage with detailed analysis?
- **Factual accuracy**: Are claims supported and accurate?

## Example Query and Response

### Query
```
Examine KKR's tech-centric transactions and their approaches to generating value. 
Investigate how they leverage technological advancements in their investment 
strategies to drive growth and enhance efficiency within portfolio companies. 
Analyze the impact of these strategies on their overall success.
```

### Expected Report Structure
```markdown
# KKR's Technology-Focused Investment Strategy and Digital Value Creation

## Executive Summary
[Overview of KKR's tech investment approach and key findings]

## Overview of KKR's Tech Investment Approach
[Historical context and strategic evolution]

## Notable Tech-Centric Transactions
[Analysis of key deals across sectors]

### Enterprise Software
[BMC Software, Epicor, Cloudera examples]

### Digital Infrastructure
[CyrusOne, Telxius, data center investments]

### Data and Analytics Services
[GfK, Internet Brands examples]

## Leveraging Technology for Operational Value Creation
[Digital transformation, AI deployment, automation]

## Impact on Investment Performance and Reputation
[Returns, market position, competitive differentiation]

## Conclusion
[Summary and forward-looking perspective]
```

## Use Cases

- **Research assistant evaluation**: Testing AI systems for research and analysis tasks
- **Enterprise AI assessment**: Evaluating models for business intelligence applications
- **Content generation benchmarking**: Comparing long-form generation capabilities
- **Model selection**: Choosing models for consulting and advisory applications

## Limitations

- **Reference bias**: Reference reports reflect Deep Research's style and approach
- **Topic coverage**: 102 topics may not cover all consulting domains
- **Temporal context**: Some topics may become outdated as markets evolve
- **Evaluation subjectivity**: Report quality assessment involves judgment

---

## Related Pages

- [Criteria Evaluation Task Type](../../task-types/criteria-evaluation.md) — How report generation evaluation works
- [Research Reports Example](../../examples/research-reports.md) — Building report generation benchmarks
- [Official Tasklists Overview](index.md) — All official PALACE tasklists
