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

"""Validate command: palace validate."""

import sys
from pathlib import Path

import click

from palace.cli.validation import Validator, Severity
from palace.download import resolve_local_path
from palace.utils.printing import print


@click.command()
@click.argument("name")
def validate(name: str) -> None:
    """Validate a benchmark tasklist.

    NAME is the benchmark name (e.g., "MMLU") or path to a tasklist directory.
    Reports errors (blocking) and warnings (non-blocking) separately.
    
    \b
    Exit codes:
        0 - Valid (no errors)
        1 - Invalid (has errors)
    
    \b
    Examples:
        palace validate MMLU
        palace validate "SWE-bench Verified"
        palace validate ./path/to/tasklist
    """
    path_or_name = name  # Use internally
    # Resolve path
    path = Path(path_or_name)
    if not path.exists():
        # Try resolving as local name (handles display names, folder names, IDs)
        resolved = resolve_local_path(path_or_name)
        if resolved:
            path = resolved
        else:
            print(f"[red]Tasklist not found:[/red] {path_or_name}")
            print("[dim]Run 'palace local' to see downloaded tasklists.[/dim]")
            sys.exit(1)
    
    print(f"[bold]Validating:[/bold] {path.name}\n")
    
    validator = Validator()
    errors, warnings = validator.validate(path)
    
    # Display errors
    if errors:
        print(f"[bold red]Errors ({len(errors)}):[/]")
        for issue in errors:
            location = ""
            if issue.path:
                location = f" [dim]{issue.path}[/]"
                if issue.field:
                    location += f"[dim]:{issue.field}[/]"
            print(f"  [red]✗[/]{location}")
            print(f"    {issue.message}")
        print()
    
    # Display warnings
    if warnings:
        print(f"[bold yellow]Warnings ({len(warnings)}):[/]")
        for issue in warnings:
            location = ""
            if issue.path:
                location = f" [dim]{issue.path}[/]"
                if issue.field:
                    location += f"[dim]:{issue.field}[/]"
            print(f"  [yellow]⚠[/]{location}")
            print(f"    {issue.message}")
        print()
    
    # Summary
    if errors:
        print(f"[red]✗ Validation failed with {len(errors)} error(s)[/red]")
        sys.exit(1)
    elif warnings:
        print(f"[green]✓ Valid[/green] [dim](with {len(warnings)} warning(s))[/dim]")
    else:
        print("[green]✓ Valid[/green]")
