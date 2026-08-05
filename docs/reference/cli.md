
Complete reference for the PALACE command-line interface.

## Quick Reference

| Command | Description |
|---------|-------------|
| `palace` | Show help and available commands |
| `palace list` | List available benchmarks |
| `palace download NAME` | Download a benchmark |
| `palace run NAME -m MODEL` | Run evaluation |
| `palace results` | List evaluation results |
| `palace config` | Show/manage configuration |
| `palace init NAME` | Create new benchmark |
| `palace validate NAME` | Validate a benchmark |
| `palace publish NAME` | Publish to HuggingFace |

## Configuration

Before running evaluations, configure your API:

```bash
palace config set url https://api.openai.com/v1
palace config set key sk-your-api-key
palace config set judge_model gpt-4o
```

View current configuration:

```bash
palace config
```

### Config Commands

| Command | Description |
|---------|-------------|
| `palace config` | Show current configuration |
| `palace config set KEY VALUE` | Set a configuration value |
| `palace config get KEY` | Get a configuration value |
| `palace config unset KEY` | Remove a configuration value |

### Available Settings

| Key | Environment Variable | Description |
|-----|---------------------|-------------|
| `url` | `OPENAI_LIKE_API_BASE_URL` | API endpoint URL |
| `key` | `OPENAI_LIKE_API_KEY` | API key |
| `judge_model` | `JUDGE_MODEL` | Model for answer verification |
| `concurrency` | `PALACE_CONCURRENCY` | Parallel tasks (default: 25) |
| `huggingface_token` | `HUGGINGFACE_TOKEN` | For gated datasets |
| `github_token` | `GITHUB_TOKEN` | For higher rate limits |
| `vivarium_url` | `VIVARIUM_URL` | Remote Vivarium URL |

Priority: CLI flags > environment variables > config file

## palace list

List available benchmarks from all sources.

```bash
palace list                  # All benchmarks
palace list --official       # Official benchmarks only
palace list --local-only     # Downloaded benchmarks only
palace list --refresh        # Force refresh from sources
```

## palace search

Search for benchmarks by name, description, or category.

```bash
palace search reasoning
palace search "expert reasoning"
palace search --refresh mmlu
```

## palace info

Show detailed information about a benchmark without downloading.

```bash
palace info MMLU
palace info "GPQA Diamond"
```

## palace download

Download benchmarks to local cache.

```bash
palace download MMLU              # Download one benchmark
palace download "GPQA Diamond"    # Names with spaces need quotes
palace download --all             # Download all benchmarks
palace download --all -y          # Skip confirmation
palace download --all --skip-existing  # Skip already downloaded
```

### Download Location

| Platform | Location |
|----------|----------|
| Linux | `~/.cache/palace/tasklists/` |
| macOS | `~/Library/Caches/palace/tasklists/` |
| Windows | `C:\Users\<user>\AppData\Local\palace\Cache\tasklists\` |

## palace local

Manage locally downloaded benchmarks.

```bash
palace local              # List local benchmarks with sizes
palace local rm NAME      # Remove a benchmark
```

## palace run

Run evaluation on a benchmark.

```bash
palace run NAME -m MODEL [options]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `NAME` | Benchmark to evaluate |
| `-m, --model` | Model name to evaluate |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-u, --url` | From config | API endpoint URL |
| `-k, --token` | From config | API key |
| `-l, --limit` | All | Maximum tasks to run |
| `-c, --concurrency` | 25 | Parallel tasks |
| `-o, --output` | `~/.cache/palace/results/` | Output directory |
| `--name` | `eval` | Run name for output file |
| `--runs` | 1 | Number of evaluation runs |
| `--agentic` | Auto | Force agentic execution via Vivarium |
| `-y, --yes` | False | Auto-confirm prompts |

### Examples

```bash
# Basic evaluation
palace run MMLU -m gpt-4o

# Limit to 10 tasks
palace run MMLU -m gpt-4o -l 10

# With specific endpoint
palace run MMLU -m gpt-4o -u https://api.example.com/v1 -k sk-xxx

# Agentic benchmark
palace run SWE-bench -m o3-mini --agentic

# Custom output
palace run MMLU -m gpt-4o -o ./my-results --name my-eval
```

## palace results

List and view evaluation results.

```bash
palace results           # List all results
palace results my-eval   # Show specific result
```

## palace init

Create a new benchmark scaffold.

```bash
palace init my-benchmark           # Interactive wizard
palace init my-benchmark --bare    # Minimal scaffold
palace init my-benchmark --agentic # Agentic benchmark scaffold
```

## palace validate

Validate a benchmark before publishing.

```bash
palace validate my-benchmark
palace validate ./path/to/benchmark
```

## palace publish

Publish a benchmark to HuggingFace.

```bash
palace publish my-benchmark
palace publish my-benchmark --org palace-ai
palace publish my-benchmark --private
palace publish my-benchmark --dry-run
palace publish my-benchmark --token hf_xxx  # Use specific token
```

## palace adapters

Manage I/O adapters for model-specific formatting.

```bash
palace adapters                    # List all adapters
palace adapters show "*Aegis*"     # Show adapter details
palace adapters match "my-model"   # Find adapter for a model
```

## palace sources

Manage benchmark sources.

```bash
palace sources              # List sources
palace sources add URL      # Add a source
palace sources rm URL       # Remove a source
```

## Deprecated Commands

The following commands are deprecated and will be removed in a future version:

| Old Command | New Command |
|-------------|-------------|
| `palace-cli` | `palace` |
| `palace-run` | `palace run` |
| `palace-download` | `palace download` |

The old commands still work but display a deprecation warning.
