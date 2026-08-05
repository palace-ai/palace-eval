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

"""Discovery commands: list, search, info."""

import json

import click

from palace.cli.git_adapters import RateLimitError, TasklistInfo, get_adapter
from palace.cli.git_adapters.local import LocalAdapter
from palace.cli.sources.manager import SourceManager
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import print


def _get_conversion_recipes() -> list[TasklistInfo]:
    """Get tasklists from conversion recipes.

    These are HuggingFace datasets that can be converted to palace format.
    """
    tasklists: list[TasklistInfo] = []

    # Load from palace/download/conversion_recipes.json
    from importlib.resources import files

    try:
        package_files = files("palace.download")
        recipes_path = package_files / "conversion_recipes.json"
        recipes_data = json.loads(recipes_path.read_text())

        for recipe in recipes_data:
            tasklists.append(
                TasklistInfo(
                    name=recipe.get("name", recipe.get("id", "unknown")),
                    source="convertible",
                    id=recipe.get("id", ""),
                    description=recipe.get("description"),
                    category=recipe.get("category"),
                    task_type=recipe.get("task_type"),
                )
            )
    except Exception:
        # Recipes file not found or invalid - try legacy location
        try:
            package_files = files("palace.entrypoints.download")
            recipes_path = package_files / "public_datasets_info.json"
            recipes_data = json.loads(recipes_path.read_text())

            for recipe in recipes_data:
                tasklists.append(
                    TasklistInfo(
                        name=recipe.get("name", recipe.get("id", "unknown")),
                        source="convertible",
                        id=recipe.get("id", ""),
                        description=recipe.get("description"),
                        category=recipe.get("category"),
                        task_type=recipe.get("task_type"),
                    )
                )
        except Exception:
            pass

    return tasklists


def _format_tasklist_line(tl: TasklistInfo, show_source: bool = True, is_local: bool = False) -> str:
    """Format a tasklist for display."""
    parts = []

    # Local indicator (downloaded)
    if is_local:
        parts.append("[green]✓[/]")
    else:
        parts.append(" ")

    # Source indicator (skip for local-only items)
    if show_source and tl.source != "local":
        source_colors = {
            "huggingface": "blue",
            "github": "white",
            "gitlab": "magenta",
            "convertible": "cyan",
        }
        color = source_colors.get(tl.source, "white")
        parts.append(f"[{color}]{tl.display_source()}[/{color}]")

    # Name (user-friendly, not the full ID)
    parts.append(f"[bold]{tl.name}[/]")

    # Official indicator (after name)
    if tl.official:
        parts.append("[yellow]⭐[/]")

    # Category
    if tl.category:
        parts.append(f"[dim]({tl.category})[/]")

    # Stars (from extra)
    stars = tl.extra.get("stars") or tl.extra.get("stargazers_count")
    if stars:
        parts.append(f"[dim]★{stars}[/]")

    # Description (truncated)
    if tl.description:
        desc = tl.description[:50]
        if len(tl.description) > 50:
            desc += "..."
        parts.append(f"[dim]- {desc}[/]")

    return " ".join(parts)


def _prompt_for_github_token() -> None:
    """Prompt user about setting GITHUB_TOKEN."""
    print()
    print("[yellow]GitHub API rate limit exceeded.[/yellow]")
    print()
    print("To increase the rate limit from 60/hr to 5000/hr, set a GitHub token:")
    print()
    print("  1. Create a token at: [blue]https://github.com/settings/tokens[/blue]")
    print("  2. Set the environment variable:")
    print("     [dim]export GITHUB_TOKEN=your_token_here[/dim]")
    print()


@click.command("list")
@click.option("--official", is_flag=True, help="Show only official tasklists.")
@click.option("--refresh", is_flag=True, help="Force refresh, ignoring cache.")
@click.option("--local-only", is_flag=True, help="Show only locally downloaded tasklists.")
def list_cmd(official: bool, refresh: bool, local_only: bool) -> None:
    """List available benchmarks from all sources."""

    # Get local tasklists first (for marking downloaded items)
    local_adapter = LocalAdapter()
    local_tasklists = local_adapter.list_tasklists()
    local_names = {tl.name for tl in local_tasklists}
    # Also track by ID for remote items
    local_ids = {tl.id for tl in local_tasklists}

    if local_only:
        if not local_tasklists:
            print("[dim]No local tasklists found. Use 'palace download' to download benchmarks.[/]")
            return

        print(f"[bold]Local tasklists[/] ({len(local_tasklists)}):")
        for tl in sorted(local_tasklists, key=lambda t: (t.category or "", t.name)):
            print(f"  {_format_tasklist_line(tl, show_source=False, is_local=True)}")
        return

    # Discover from all sources
    manager = SourceManager()
    errors: list[tuple[str, str]] = []

    def on_error(source, exc):
        errors.append((source.key(), str(exc)))

    try:
        remote_tasklists = manager.discover_all(refresh=refresh, on_error=on_error)
    except RateLimitError:
        _prompt_for_github_token()
        return

    # Add conversion recipes
    recipes = _get_conversion_recipes()

    # Build unified list: remote + recipes, marking which are local
    # Use a dict to deduplicate by a normalized key (lowercase name)
    all_items: dict[str, TasklistInfo] = {}

    # Add remote items first
    for tl in remote_tasklists:
        key = tl.name.lower()
        if key not in all_items:
            all_items[key] = tl

    # Add recipes (don't override remote items which have more info)
    for tl in recipes:
        key = tl.name.lower()
        if key not in all_items:
            all_items[key] = tl

    # Add local-only items (not found remotely)
    for tl in local_tasklists:
        key = tl.name.lower()
        if key not in all_items:
            # Local-only item, add it
            all_items[key] = tl

    all_tasklists = list(all_items.values())

    # Filter official if requested
    if official:
        all_tasklists = [tl for tl in all_tasklists if tl.official]

    if not all_tasklists:
        if official:
            print("[dim]No official tasklists found.[/]")
        else:
            print("[dim]No tasklists found.[/]")
        return

    # Sort by category, then name
    all_tasklists.sort(key=lambda t: (t.category or "zzz", t.name))

    # Display
    title = "Official tasklists" if official else "Available tasklists"
    print(f"[bold]{title}[/] ({len(all_tasklists)}):")

    for tl in all_tasklists:
        # Check if this item is downloaded locally
        is_local = tl.name.lower() in {n.lower() for n in local_names} or tl.id in local_ids
        print(f"  {_format_tasklist_line(tl, is_local=is_local)}")

    # Show errors if any
    if errors:
        print()
        print(f"[yellow]Warning: {len(errors)} source(s) failed to respond[/]")


@click.command()
@click.argument("query")
@click.option("--refresh", is_flag=True, help="Force refresh, ignoring cache.")
def search(query: str, refresh: bool) -> None:
    """Search for benchmarks matching QUERY.

    Searches benchmark names, descriptions, and categories.
    Multiple words are matched independently (all must appear).
    """
    # Split query into words for matching
    # TODO: Consider proper ranking (BM25/TF-IDF) when catalog grows to 1000+
    query_words = query.lower().split()

    # Get local tasklists first (for marking downloaded items)
    local_adapter = LocalAdapter()
    local_tasklists = local_adapter.list_tasklists()
    local_names = {tl.name.lower() for tl in local_tasklists}

    # Get all remote tasklists
    manager = SourceManager()

    try:
        remote_tasklists = manager.discover_all(refresh=refresh)
    except RateLimitError:
        _prompt_for_github_token()
        return

    # Add conversion recipes
    recipes = _get_conversion_recipes()

    # Combine all
    all_tasklists = remote_tasklists + recipes + local_tasklists

    # Search: all query words must appear in name, description, or category
    def matches(tl: TasklistInfo) -> bool:
        text = f"{tl.name} {tl.description or ''} {tl.category or ''}".lower()
        return all(word in text for word in query_words)

    matches_list = [tl for tl in all_tasklists if matches(tl)]

    # Deduplicate by lowercase name
    seen_names: set[str] = set()
    unique_matches: list[TasklistInfo] = []
    for tl in matches_list:
        key = tl.name.lower()
        if key not in seen_names:
            seen_names.add(key)
            unique_matches.append(tl)

    if not unique_matches:
        print(f"[dim]No tasklists found matching '{query}'[/]")
        return

    unique_matches.sort(key=lambda t: (t.category or "zzz", t.name))

    print(f"[bold]Search results for '{query}'[/] ({len(unique_matches)}):")
    for tl in unique_matches:
        is_local = tl.name.lower() in local_names
        print(f"  {_format_tasklist_line(tl, is_local=is_local)}")


@click.command()
@click.argument("name")
def info(name: str) -> None:
    """Show detailed info for a benchmark without downloading.

    NAME is the benchmark name (e.g., "MMLU", "GPQA Diamond").
    """
    ref = name  # Use 'ref' internally
    ref_lower = ref.lower()

    # Check local first (by name, checking info.json)
    local_adapter = LocalAdapter()
    for tl in local_adapter.list_tasklists():
        if tl.name.lower() == ref_lower or tl.id.lower() == ref_lower:
            folder = tl.extra.get("folder", tl.name)
            local_path = TASKLISTS_PATH / folder
            if (local_path / "info.json").exists():
                try:
                    info_data = json.loads((local_path / "info.json").read_text())
                    _display_info(tl.id, info_data, source="local")
                    return
                except Exception as e:
                    print(f"[red]Error reading local info.json: {e}[/]")
                    return

    # Check conversion recipes
    recipes = _get_conversion_recipes()
    for recipe in recipes:
        if recipe.name.lower() == ref_lower:
            print(f"[bold]{recipe.name}[/] [cyan][convertible][/]\n")
            if recipe.description:
                print(f"  {recipe.description}\n")
            if recipe.category:
                print(f"  Category: {recipe.category}")
            if recipe.task_type:
                print(f"  Task type: {recipe.task_type}")
            print("\n  [dim]This is a HuggingFace dataset that will be converted to palace format on download.[/]")
            print(f'  [dim]Run: palace download "{recipe.name}"[/]')
            return

    # Search all configured sources
    manager = SourceManager()
    try:
        remote_tasklists = manager.discover_all(refresh=False)
    except RateLimitError:
        _prompt_for_github_token()
        return
    except Exception:
        remote_tasklists = []

    # Find by name
    for tl in remote_tasklists:
        if tl.name.lower() == ref_lower:
            # Found it - fetch full info
            try:
                adapter = get_adapter(tl.source)
                info_data = adapter.get_info(tl.id)
                _display_info(tl.id, info_data, source=tl.source)
                return
            except FileNotFoundError:
                # No info.json, show what we have from discovery
                print(f"[bold]{tl.name}[/] [{tl.source}]\n")
                if tl.description:
                    print(f"  {tl.description}\n")
                print(f"  ID: {tl.id}")
                if tl.category:
                    print(f"  Category: {tl.category}")
                if tl.task_type:
                    print(f"  Task type: {tl.task_type}")
                print(f'\n  [dim]Download: palace download "{tl.name}"[/]')
                return
            except Exception as e:
                print(f"[red]Error fetching info: {e}[/]")
                return

    # Also try by ID if ref contains /
    if "/" in ref:
        for tl in remote_tasklists:
            if tl.id.lower() == ref_lower:
                try:
                    adapter = get_adapter(tl.source)
                    info_data = adapter.get_info(tl.id)
                    _display_info(tl.id, info_data, source=tl.source)
                    return
                except Exception as e:
                    print(f"[red]Error fetching info: {e}[/]")
                    return

    print(f"[red]Tasklist not found: {ref}[/]")
    print("[dim]Try 'palace list' to see available tasklists.[/]")
    print("[dim]Try 'palace list' to see available tasklists.[/]")


def _display_info(ref: str, info_data: dict, source: str) -> None:
    """Display formatted info.json contents."""
    name = info_data.get("name", ref.split("/")[-1] if "/" in ref else ref)

    source_label = {
        "local": "[green][local][/]",
        "huggingface": "[blue][HF][/]",
        "github": "[white][GitHub][/]",
        "gitlab": "[magenta][GitLab][/]",
    }.get(source, f"[{source}]")

    print(f"[bold]{name}[/] {source_label}\n")

    if info_data.get("description"):
        print(f"  {info_data['description']}\n")

    # Show ID if different from name (for remote sources)
    if "/" in ref:
        print(f"  ID: {ref}")

    # Core fields
    fields = [
        ("Category", info_data.get("category")),
        ("Task type", info_data.get("task_type")),
        ("Input modalities", info_data.get("input_modalities", info_data.get("modalities"))),
        ("Output modalities", info_data.get("output_modalities")),
    ]

    for label, value in fields:
        if value:
            if isinstance(value, list):
                value = ", ".join(value)
            print(f"  {label}: {value}")

    # Task type specific fields
    task_type_fields = info_data.get("task_type_fields", {})
    if task_type_fields:
        print()
        for key, value in task_type_fields.items():
            print(f"  {key}: {value}")

    # Agentic env
    if "env" in info_data:
        env = info_data["env"]
        print()
        print("  [bold]Agentic environment:[/]")
        if "image" in env:
            print(f"    Image: {env['image']}")
        if "tools" in env:
            print(f"    Tools: {', '.join(env['tools'])}")

    # Download hint for remote sources
    if source != "local":
        print()
        print(f'  [dim]Download: palace download "{name}"[/]')
