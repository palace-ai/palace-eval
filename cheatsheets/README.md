# PALACE Cheatsheets

Quick reference materials for creating PALACE tasklists.

## Available Documents

| Document | Description |
|----------|-------------|
| [reference-sheet.pdf](reference-sheet.pdf) | Complete reference for all 5 task types, JSON schemas, and common patterns |
| [agentic-tutorial.pdf](agentic-tutorial.pdf) | Step-by-step tutorial for building an agentic benchmark |

## Compatibility

These cheatsheets are compatible with **palace-eval 1.0.x**. Check the version note in the PDF header to ensure you're using documentation that matches your installed version.

## Building from Source

The PDFs are built from LaTeX source using [Tectonic](https://tectonic-typesetting.github.io/).

```bash
# Install tectonic (via conda)
conda install -c conda-forge tectonic

# Build PDFs
cd palace-eval/cheatsheets
tectonic reference-sheet.tex
tectonic agentic-tutorial.tex
```

## Files

- `cheatsheets.sty` — Shared LaTeX style (A3 landscape, multi-column)
- `reference-sheet.tex` — Main cheatsheet source
- `agentic-tutorial.tex` — Tutorial source

## Contributing

If you edit the `.tex` files, please rebuild the PDFs before committing:

```bash
tectonic reference-sheet.tex
tectonic agentic-tutorial.tex
```
