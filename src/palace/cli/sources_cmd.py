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

"""Source management commands: sources add/rm."""

import click

from palace.cli.sources.manager import SourceManager
from palace.utils.printing import print


@click.group(invoke_without_command=True)
@click.pass_context
def sources(ctx: click.Context) -> None:
    """Manage benchmark sources.
    
    Sources are locations where palace looks for benchmarks. They are organized
    by trust level:
    
    \b
    - Official: Curated benchmarks from the palace team
    - Community: Public benchmarks from anyone (HuggingFace, GitHub)
    - User: Sources you've added (orgs, collections, local paths)
    """
    if ctx.invoked_subcommand is None:
        # List all sources
        manager = SourceManager()
        
        print("[bold]Official[/] (curated by palace team):")
        print("  [blue][HF][/] palace-ai ⭐")
        
        print("\n[bold]Community[/] (public, anyone can publish):")
        print("  [blue][HF][/] public datasets with palace-tasklist tag")
        print("  [white][GitHub][/] public repos with palace-tasklist topic")
        
        user_sources = manager.get_user_sources()
        if user_sources:
            print("\n[bold]User sources[/] (your additions):")
            for source in user_sources:
                _print_source(source)
        else:
            print("\n[dim]No user sources configured.[/]")
            print("[dim]Add sources with: palace sources add <url>[/]")


def _print_source(source) -> None:
    """Print a formatted user source line."""
    type_colors = {
        "huggingface": "blue",
        "github": "white",
        "gitlab": "magenta",
        "local": "green",
    }
    color = type_colors.get(source.type, "white")
    
    # Build description
    collection_name = source.extra.get("collection_name") if source.extra else None
    if collection_name:
        desc = f"collection:{collection_name}"
    elif source.org:
        desc = f"org:{source.org}"
    elif source.url:
        desc = source.url
    else:
        desc = source.tag
    
    print(f"  [{color}][{source.type}][/{color}] {desc}")


@sources.command()
@click.argument("url")
def add(url: str) -> None:
    """Add a benchmark source URL.
    
    URL can be:
    
    \b
    - HuggingFace org: https://huggingface.co/my-org
    - HuggingFace collection: https://huggingface.co/collections/org/name
    - GitHub org: https://github.com/my-org
    - GitLab group: https://gitlab.com/my-group
    - Local path: /path/to/tasklists
    
    The source type is auto-detected from the URL.
    """
    manager = SourceManager()
    
    try:
        source = manager.add_source(url)
        print(f"[green]Added source:[/] [{source.type}] {url}")
        
        # Show hint based on source type
        collection_slug = source.extra.get("collection_slug") if source.extra else None
        if collection_slug:
            print(f"[dim]This will list datasets from the collection[/]")
        elif source.org:
            print(f"[dim]This will search for repos with 'palace-tasklist' tag in {source.org}[/]")
        
    except ValueError as e:
        print(f"[red]Error:[/] {e}")
        raise SystemExit(1)


@sources.command()
@click.argument("url")
def rm(url: str) -> None:
    """Remove a benchmark source URL.
    
    Only user-added sources can be removed. Default sources cannot be removed.
    """
    manager = SourceManager()
    
    if manager.remove_source(url):
        print(f"[green]Removed source:[/] {url}")
    else:
        print(f"[yellow]Source not found:[/] {url}")
        print("[dim]Note: Default sources cannot be removed.[/]")
