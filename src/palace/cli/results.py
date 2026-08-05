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

"""Results command: palace results."""

import json
from datetime import datetime
from pathlib import Path

import click

from palace.utils.paths import RESULTS_PATH
from palace.utils.printing import print


@click.command()
@click.argument("id", required=False)
def results(id: str | None) -> None:
    """List or show evaluation results.

    Without arguments, lists all results sorted by date (newest first).
    With ID, shows detailed results for that evaluation.
    
    \b
    Examples:
        palace results
        palace results my-eval
    """
    result_id = id  # Use internally
    if result_id:
        _show_result(result_id)
    else:
        _list_results()


def _list_results() -> None:
    """List all results sorted by date."""
    if not RESULTS_PATH.exists():
        print("[dim]No results found.[/dim]")
        print("[dim]Run 'palace run' to generate results.[/dim]")
        return
    
    # Find all result files (JSONL)
    result_files: list[tuple[Path, datetime]] = []
    
    for path in RESULTS_PATH.rglob("*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            result_files.append((path, mtime))
        except Exception:
            continue
    
    if not result_files:
        print("[dim]No results found.[/dim]")
        print("[dim]Run 'palace run' to generate results.[/dim]")
        return
    
    # Sort by modification time (newest first)
    result_files.sort(key=lambda x: x[1], reverse=True)
    
    print(f"[bold]Evaluation results[/bold] ({len(result_files)}):\n")
    
    for path, mtime in result_files[:20]:  # Show last 20
        # Try to extract info from file
        try:
            with open(path) as f:
                first_line = f.readline()
                if first_line:
                    data = json.loads(first_line)
                    model = data.get("model", "unknown")
                    tasklist = data.get("tasklist", "unknown")
                    accuracy = data.get("accuracy")
                    
                    acc_str = f"[green]{accuracy:.1%}[/green]" if accuracy else "[dim]N/A[/dim]"
                    date_str = mtime.strftime("%Y-%m-%d %H:%M")
                    
                    print(f"  [bold]{path.stem}[/bold]")
                    print(f"    Model: {model} | Tasklist: {tasklist} | Accuracy: {acc_str}")
                    print(f"    [dim]{date_str} - {path}[/dim]")
                    print()
        except Exception:
            # Fallback to just showing the file
            date_str = mtime.strftime("%Y-%m-%d %H:%M")
            print(f"  [bold]{path.stem}[/bold]")
            print(f"    [dim]{date_str} - {path}[/dim]")
            print()
    
    if len(result_files) > 20:
        print(f"[dim]... and {len(result_files) - 20} more results[/dim]")


def _show_result(result_id: str) -> None:
    """Show detailed results for a specific evaluation."""
    # Try to find the result file
    result_path = None
    
    # Try exact path
    if Path(result_id).exists():
        result_path = Path(result_id)
    else:
        # Search in results directory
        for path in RESULTS_PATH.rglob("*.jsonl"):
            if path.stem == result_id or result_id in str(path):
                result_path = path
                break
    
    if not result_path or not result_path.exists():
        print(f"[red]Result not found:[/red] {result_id}")
        print("[dim]Run 'palace results' to see available results.[/dim]")
        return
    
    # Read and display
    print(f"[bold]Result: {result_path.stem}[/bold]\n")
    print(f"[dim]File: {result_path}[/dim]\n")
    
    try:
        with open(result_path) as f:
            lines = f.readlines()
        
        if not lines:
            print("[dim]Empty result file.[/dim]")
            return
        
        # First line is summary
        summary = json.loads(lines[0])
        
        print("[bold]Summary:[/bold]")
        print(f"  Model: {summary.get('model', 'N/A')}")
        print(f"  Tasklist: {summary.get('tasklist', 'N/A')}")
        print(f"  Tasks: {summary.get('total_tasks', 'N/A')}")
        
        if "accuracy" in summary:
            print(f"  Accuracy: [green]{summary['accuracy']:.1%}[/green]")
        
        if "pass_at_k" in summary:
            for k, v in summary["pass_at_k"].items():
                print(f"  pass@{k}: {v:.1%}")
        
        if "metrics" in summary:
            print("\n[bold]Metrics:[/bold]")
            for key, value in summary["metrics"].items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value}")
        
        # Show per-task breakdown if available
        if len(lines) > 1:
            correct = sum(1 for line in lines[1:] if json.loads(line).get("correct"))
            total = len(lines) - 1
            print(f"\n[bold]Tasks:[/bold] {correct}/{total} correct")
        
    except json.JSONDecodeError as e:
        print(f"[red]Error parsing result file:[/red] {e}")
    except Exception as e:
        print(f"[red]Error reading result:[/red] {e}")
