# Copyright (C) 2025 European Union
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the European Union Public Licence (EUPL) v. 1.2
# as published by the European Union.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# European Union Public Licence for more details.
#
# You should have received a copy of the European Union Public Licence
# along with this program. If not, see <https://joinup.ec.europa.eu/collection/eupl/eupl-text-eupl-12>.

"""Run command: palace run."""

import json
import sys

import click
import questionary

from palace.download import download_by_name, is_downloaded
from palace.utils.config import get_config_value
from palace.utils.paths import RESULTS_PATH, TASKLISTS_PATH
from palace.utils.printing import print


def _parse_param_value(value: str):
    """Parse a param value: try JSON literal (number, bool, object), fallback to string."""
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


@click.command()
@click.argument("name", required=False, default=None)
@click.option("--model", "-m", default=None, help="Model name to evaluate.")
@click.option("--url", "-u", default=None, help="API endpoint URL. Defaults to OPENAI_LIKE_API_BASE_URL.")
@click.option("--token", "-k", default=None, help="API token. Defaults to OPENAI_LIKE_API_KEY.")
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm download prompts (for CI).")
@click.option("--limit", "-l", type=int, default=None, help="Maximum tasks to evaluate.")
@click.option("--runs", "-r", type=int, default=1, help="Number of runs per configuration.")
@click.option("--output", "-o", default=None, help="Output folder for results.")
@click.option("--agentic", "-a", is_flag=True, help="Force agentic execution via Vivarium.")
@click.option("--concurrency", "-c", type=int, default=None, help="Number of concurrent tasks.")
@click.option("--name", "-n", "run_name", default="eval", help="Name for this evaluation run.")
@click.option(
    "--endpoint-type",
    "-e",
    "endpoint_type",
    type=click.Choice(["openai", "anthropic", "azure", "mcp"]),
    default=None,
    help="API type. Auto-detected from model name if not specified (e.g., 'claude' → anthropic).",
)
@click.option(
    "--param",
    "-p",
    "params",
    multiple=True,
    metavar="KEY=VALUE",
    help="Extra model parameter (e.g., -p reasoning_effort=high -p temperature=0.5). Can be specified multiple times.",
)
@click.option(
    "--vivarium-url", default=None, help="Vivarium service URL. Defaults to vivarium_url config/VIVARIUM_URL env."
)
def run(
    name: str | None,
    model: str | None,
    url: str | None,
    token: str | None,
    yes: bool,
    limit: int | None,
    runs: int,
    output: str | None,
    agentic: bool,
    concurrency: int | None,
    run_name: str,
    endpoint_type: str | None,
    params: tuple[str, ...],
    vivarium_url: str | None,
) -> None:
    """Run evaluation on a benchmark.

    NAME is the benchmark to evaluate (e.g., "MMLU", "GPQA Diamond").
    Downloads automatically if not found locally.
    Without arguments, launches an interactive wizard.

    \b
    Examples:
        palace run MMLU -m gpt-4o
        palace run "GPQA Diamond" -m claude-3-5-sonnet -l 10
        palace run SWE-bench -m o3-mini --agentic -y
        palace run
    """
    # --- Wizard mode: invoked with no arguments (exactly "palace run") ---
    # Check sys.argv since Click has already parsed; argv[0]=palace, argv[1]=run
    if len(sys.argv) == 2:
        from palace.cli.wizard import run_wizard

        run_wizard()
        return

    # --- Validate required arguments ---
    if not name:
        print("[red]Error:[/red] Missing benchmark name.")
        print("[dim]Usage: palace run <benchmark> -m <model>[/dim]")
        print("[dim]   or: palace run  (for interactive wizard)[/dim]")
        sys.exit(1)
    if not model:
        print("[red]Error:[/red] Missing model. Use -m/--model to specify.")
        print(f"[dim]Usage: palace run {name} -m <model>[/dim]")
        sys.exit(1)

    benchmark = name  # Use 'benchmark' internally

    # Get URL and token: CLI flags > env vars > config file
    url = url or get_config_value("url")
    token = token or get_config_value("key")
    vivarium_url = vivarium_url or get_config_value("vivarium_url")

    if not url:
        print("[red]Error: API URL not configured.[/red]\n")
        print("Set up with:")
        print("  [cyan]palace config set url https://api.openai.com/v1[/cyan]")
        print("  [cyan]palace config set key sk-...[/cyan]")
        print()
        print("Or pass directly:")
        print("  [dim]palace run MMLU -m gpt-4o -u <url> -k <key>[/dim]")
        print()
        print("Run [cyan]palace config[/cyan] to see current configuration.")
        sys.exit(1)

    # Token is optional — local/unauthenticated endpoints don't need it.
    # The API will return 401 if auth is actually required.

    # Check if benchmark exists locally
    if not is_downloaded(benchmark):
        # Try case-insensitive match
        local_match = None
        for d in TASKLISTS_PATH.iterdir():
            if d.is_dir() and d.name.lower() == benchmark.lower():
                local_match = d.name
                break

        if local_match:
            benchmark = local_match
        else:
            # Benchmark not found locally - prompt to download
            if yes:
                print(f"[yellow]Benchmark '{benchmark}' not found locally. Downloading...[/yellow]")
                try:
                    download_by_name(benchmark)
                except ValueError:
                    print(f"[red]Error:[/red] Unknown benchmark: {benchmark}")
                    print("[dim]Run 'palace list' to see available benchmarks.[/dim]")
                    sys.exit(1)
                except Exception as e:
                    print(f"[red]Download failed:[/red] {e}")
                    sys.exit(1)
            else:
                # Interactive prompt
                answer = questionary.confirm(
                    f"Benchmark '{benchmark}' not found locally. Download now?",
                    default=True,
                ).ask()

                if answer is None:
                    # User cancelled
                    sys.exit(130)

                if answer:
                    try:
                        download_by_name(benchmark)
                    except ValueError:
                        print(f"[red]Error:[/red] Unknown benchmark: {benchmark}")
                        print("[dim]Run 'palace list' to see available benchmarks.[/dim]")
                        sys.exit(1)
                    except Exception as e:
                        print(f"[red]Download failed:[/red] {e}")
                        sys.exit(1)
                else:
                    print("[dim]Evaluation cancelled.[/dim]")
                    sys.exit(0)

    # Run evaluation
    try:
        from pathlib import Path

        from palace.agents import ModelNotFoundError
        from palace.evaluation import Evaluation
        from palace.utils.exceptions import JudgeConfigurationError

        output_path = Path(output) if output else RESULTS_PATH

        # Parse --param flags into dict
        model_extra_params = None
        if params:
            model_extra_params = {}
            for item in params:
                if "=" not in item:
                    print(f"[red]Error:[/red] --param must be KEY=VALUE, got: {item}")
                    sys.exit(1)
                key, value = item.split("=", 1)
                model_extra_params[key] = _parse_param_value(value)

        evaluation = Evaluation(
            name=run_name,
            url=url,
            token=token,
            endpoint_type=endpoint_type,
            agentic=True if agentic else None,
            vivarium_url=vivarium_url,
            task_amount_limit=limit,
            runs_per_configuration=runs,
            output_path=output_path,
            concurrency=concurrency,
            model_extra_params=model_extra_params,
        )

        evaluation.evaluate_all([model], tasklists=[benchmark])

    except FileNotFoundError as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except ModelNotFoundError as e:
        print(f"[red]Error:[/red] {e}")
        print()
        print("[dim]Check that the model name is correct and available on the endpoint.[/dim]")
        sys.exit(1)
    except JudgeConfigurationError as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
