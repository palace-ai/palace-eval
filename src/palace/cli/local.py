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

"""Local tasklist management commands: local, local rm."""

import shutil

import click

from palace.cli.git_adapters.local import LocalAdapter
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import print


def _id_to_folder(identifier: str) -> str:
    """Convert an identifier (org/name or name) to folder name."""
    return identifier.replace("/", "--")


def _find_local_tasklist(identifier: str) -> tuple[str, str] | None:
    """Find a local tasklist by name, ID, or folder.

    Args:
        identifier: Can be the name, "org/name" ID, or folder name

    Returns:
        Tuple of (folder_name, display_name) if found, None otherwise.
    """
    adapter = LocalAdapter()
    tasklists = adapter.list_tasklists()

    identifier_lower = identifier.lower()

    # Try exact match on name first (most user-friendly)
    for tl in tasklists:
        if tl.name.lower() == identifier_lower:
            return tl.extra.get("folder", tl.name), tl.name

    # Try exact match on ID (org/name)
    for tl in tasklists:
        if tl.id.lower() == identifier_lower:
            return tl.extra.get("folder", tl.id), tl.name

    # Try folder name (org--name format)
    folder_name = _id_to_folder(identifier)
    for tl in tasklists:
        if tl.extra.get("folder", "").lower() == folder_name.lower():
            return tl.extra.get("folder"), tl.name

    return None


@click.group(invoke_without_command=True)
@click.pass_context
def local(ctx: click.Context) -> None:
    """Manage locally downloaded benchmarks.

    Without a subcommand, lists all local benchmarks.
    """
    if ctx.invoked_subcommand is None:
        # List local tasklists
        adapter = LocalAdapter()
        tasklists = adapter.list_tasklists()

        if not tasklists:
            print("[dim]No local tasklists found.[/]")
            print("[dim]Use 'palace download <name>' to download benchmarks.[/]")
            return

        # Calculate total size
        total_size = 0
        for tl in tasklists:
            folder = tl.extra.get("folder", tl.name)
            path = TASKLISTS_PATH / folder
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        total_size += f.stat().st_size

        print(f"[bold]Local tasklists[/] ({len(tasklists)}, {_format_size(total_size)}):")

        # Sort by category
        tasklists.sort(key=lambda t: (t.category or "zzz", t.id))

        for tl in tasklists:
            # Get size using folder name
            folder = tl.extra.get("folder", tl.name)
            path = TASKLISTS_PATH / folder
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.exists() else 0

            category = f"[dim]({tl.category})[/]" if tl.category else ""
            size_str = f"[dim]{_format_size(size)}[/]"

            # Description (truncated)
            desc = ""
            if tl.description:
                d = tl.description[:40]
                if len(tl.description) > 40:
                    d += "..."
                desc = f" [dim]- {d}[/]"

            # Show name (user-friendly), with ID hint if different
            display_name = tl.name
            if "/" in tl.id and tl.id.split("/")[-1] != tl.name:
                # ID and name differ, show both
                display_name = f"{tl.name} [dim]({tl.id})[/]"

            print(f"  [bold]{display_name}[/] {category} {size_str}{desc}")


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


@local.command()
@click.argument("name")
def rm(name: str) -> None:
    """Remove a locally downloaded benchmark.

    NAME is the benchmark name (e.g., "MMLU") or full ID (e.g., "org/name").
    Deletes immediately without confirmation. Re-download with 'palace download'.
    """
    identifier = name  # Use internally
    result = _find_local_tasklist(identifier)

    if not result:
        print(f"[red]Tasklist not found:[/] {identifier}")
        print("[dim]Run 'palace local' to see downloaded tasklists.[/]")
        return

    folder_name, display_id = result
    path = TASKLISTS_PATH / folder_name

    try:
        shutil.rmtree(path)
        print(f"[green]Removed:[/] {display_id}")
    except Exception as e:
        print(f"[red]Failed to remove {display_id}:[/] {e}")
