# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in PALACE, please report it responsibly.

### How to Report

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email us at:

* massimiliano.altieri@ec.europa.eu

Include the following in your report:

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Any suggested fixes (optional)

### What to Expect

We will assess the report and work with you on a fix. If desired, we will credit you in the release notes.

### Scope

This security policy covers:

* The `palace-eval` Python package
* Official benchmark tasklists distributed via HuggingFace
* Documentation and example code

Out of scope:

* Third-party dependencies (report to respective maintainers)
* User-created custom tasklists
* Deployment configurations

## Security Considerations

### API Keys

PALACE requires API keys for LLM endpoints. Best practices:

* Never commit `.env` files or API keys to version control
* Use environment variables or secure secret management
* Rotate keys periodically

### Agentic Evaluation

When running agentic benchmarks with Vivarium:

* Agents execute in sandboxed Docker containers
* Network access is controlled per-benchmark
* Review benchmark requirements before enabling tool access

### Data Privacy

* Evaluation prompts are sent to your configured LLM endpoint
* Results are stored locally by default
* No telemetry or data collection by PALACE itself
