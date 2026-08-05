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
import os
import sys

import click
import questionary

from palace.download import download_by_name, is_downloaded
from palace.utils.paths import TASKLISTS_PATH, RESULTS_PATH
from palace.utils.printing import print
from palace.utils.config import get_config_value


@click.command()
@click.argument("name")
@click.option("--model", "-m", required=True, help="Model name to evaluate.")
@click.option("--url", "-u", default=None, help="API endpoint URL. Defaults to OPENAI_LIKE_API_BASE_URL.")
@click.option("--token", "-k", default=None, help="API token. Defaults to OPENAI_LIKE_API_KEY.")
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm download prompts (for CI).")
@click.option("--limit", "-l", type=int, default=None, help="Maximum tasks to evaluate.")
@click.option("--runs", type=int, default=1, help="Number of runs per configuration.")
@click.option("--output", "-o", default=None, help="Output folder for results.")
@click.option("--agentic", is_flag=True, help="Force agentic execution via Vivarium.")
@click.option("--concurrency", "-c", type=int, default=None, help="Number of concurrent tasks.")
@click.option("--name", "run_name", default="eval", help="Name for this evaluation run.")
def run(
    name: str,
    model: str,
    url: str | None,
    token: str | None,
    yes: bool,
    limit: int | None,
    runs: int,
    output: str | None,
    agentic: bool,
    concurrency: int | None,
    run_name: str,
) -> None:
    """Run evaluation on a benchmark.

    NAME is the benchmark to evaluate (e.g., "MMLU", "GPQA Diamond").
    Downloads automatically if not found locally.
    
    \b
    Examples:
        palace run MMLU -m gpt-4o
        palace run "GPQA Diamond" -m claude-3-5-sonnet -l 10
        palace run SWE-bench -m o3-mini --agentic -y
    """
    benchmark = name  # Use 'benchmark' internally
    
    # Get URL and token: CLI flags > env vars > config file
    url = url or get_config_value("url")
    token = token or get_config_value("key")
    
    if not url or not token:
        print("[red]Error: API not configured.[/red]\n")
        print("Set up with:")
        print("  [cyan]palace config set url https://api.openai.com/v1[/cyan]")
        print("  [cyan]palace config set key sk-...[/cyan]")
        print()
        print("Or pass directly:")
        print("  [dim]palace run MMLU -m gpt-4o -u <url> -k <key>[/dim]")
        print()
        print("Run [cyan]palace config[/cyan] to see current configuration.")
        sys.exit(1)
    
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
        from palace.evaluation import Evaluation
        
        output_path = Path(output) if output else RESULTS_PATH
        
        evaluation = Evaluation(
            name=run_name,
            url=url,
            token=token,
            agentic=True if agentic else None,
            task_amount_limit=limit,
            runs_per_configuration=runs,
            output_path=output_path,
            concurrency=concurrency,
        )
        
        evaluation.evaluate_all([model], tasklists=[benchmark])
        
    except FileNotFoundError as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"[red]Error:[/red] {e}")
        sys.exit(1)
