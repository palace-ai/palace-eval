# Contributing to PALACE

Thank you for your interest in contributing to PALACE! This document provides guidelines for contributing to the project.

## Ways to Contribute

- **Report bugs** - Open an issue describing the problem
- **Suggest features** - Open an issue with your proposal
- **Add benchmarks** - Create new tasklists following our format
- **Improve documentation** - Fix typos, clarify explanations, add examples
- **Submit code** - Fix bugs or implement new features

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/palace-eval.git
   cd palace-eval
   ```
3. Install in development mode with dev dependencies:
   ```bash
   uv sync --all-extras    # installs package + dev dependencies (ruff, pytest)
   ```
4. Create a branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

PALACE requires Python 3.13+. We use [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
uv sync --all-extras      # install with dev dependencies
uv run palace --help      # verify installation
```

A pre-commit hook runs Ruff automatically on commit. The hook is local to your clone (in `.git/hooks/`), so you may want to set it up:

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
set -e
uv run ruff check --fix .
uv run ruff format .
git add -u
EOF
chmod +x .git/hooks/pre-commit
```

## Code Style

- Follow [PEP 8](https://pep8.org/) conventions
- Use type hints for function signatures
- Write docstrings for public functions and classes
- Keep functions focused and reasonably sized

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
uv run ruff check src/       # lint
uv run ruff check --fix .    # lint and auto-fix
uv run ruff format src/      # format
```

## Testing

Before submitting a PR, verify that:

1. The package imports correctly:
   ```bash
   python -c "from palace import evaluate; print('OK')"
   ```

2. Basic functionality works:
   ```bash
   palace-download -t SimpleQA --skip-existing
   palace-run -u YOUR_ENDPOINT -m YOUR_MODEL -t SimpleQA -l 5
   ```

## Submitting Changes

1. Commit your changes with clear, descriptive messages
2. Push to your fork
3. Open a Pull Request against the `main` branch
4. Describe your changes and link any related issues

### Pull Request Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Add an entry to CHANGELOG.md under "Unreleased"
- Ensure all existing functionality still works

## Adding New Benchmarks

To contribute a new benchmark tasklist:

1. Create a folder in the tasklists format:
   ```
   MyBenchmark/
   +-- info.json      # metadata
   +-- tasks.json     # task definitions
   +-- task_files/    # optional attachments
   ```

2. Follow the task type specification in the documentation

3. Test locally by placing in `~/.cache/palace/tasklists/`

4. For inclusion in the official distribution, open a PR with:
   - The tasklist files
   - Documentation in `docs/reference/tasklists/`
   - Entry in the download registry

## License

By contributing, you agree that your contributions will be licensed under the [EUPL-1.2](LICENSE).

## Questions?

- Open a [GitHub Issue](https://github.com/palace-ai/palace-eval/issues)
- Email: massimiliano.altieri@ec.europa.eu

Thank you for helping improve PALACE!
