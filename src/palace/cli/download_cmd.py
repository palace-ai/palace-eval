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

"""Download command: palace download."""

from pathlib import Path

import click

from palace.cli.git_adapters import get_adapter, TasklistInfo
from palace.cli.sources.manager import SourceManager
from palace.download import download_by_name, list_downloadable, is_downloaded, DownloadEvent
from palace.utils.paths import TASKLISTS_PATH
from palace.utils.printing import print


def _find_tasklist(ref: str) -> TasklistInfo | None:
    """Find a tasklist by name or ID from all sources.
    
    Args:
        ref: Name (e.g., "MMLU") or full ID (e.g., "altiema/my-benchmark")
        
    Returns:
        TasklistInfo if found, None otherwise.
    """
    ref_lower = ref.lower()
    
    # First check conversion recipes (legacy download system)
    available = list_downloadable(skip_existing=False)
    for item in available:
        if item["name"].lower() == ref_lower:
            return TasklistInfo(
                name=item["name"],
                source="convertible",
                id=item.get("id", item["name"]),
                category=item.get("category"),
            )
    
    # Then check all configured sources
    manager = SourceManager()
    try:
        remote_tasklists = manager.discover_all(refresh=False)
    except Exception:
        remote_tasklists = []
    
    # Search by exact name first (most common case)
    for tl in remote_tasklists:
        if tl.name.lower() == ref_lower:
            return tl
    
    # Then try exact ID match
    for tl in remote_tasklists:
        if tl.id.lower() == ref_lower:
            return tl
    
    # Try partial match on name
    partial_matches = [tl for tl in remote_tasklists if ref_lower in tl.name.lower()]
    if len(partial_matches) == 1:
        return partial_matches[0]
    
    return None


def _download_all_tasklists(skip_existing: bool, auto_confirm: bool) -> None:
    """Download all available tasklists.
    
    Args:
        skip_existing: Skip tasklists that are already downloaded.
        auto_confirm: Skip confirmation prompt.
    """
    import questionary
    
    # Discover all available tasklists
    print("[dim]Discovering available benchmarks...[/]")
    
    # Get conversion recipes
    available = list_downloadable(skip_existing=False)
    
    # Get remote tasklists
    manager = SourceManager()
    try:
        remote_tasklists = manager.discover_all(refresh=False)
    except Exception as e:
        print(f"[yellow]Warning:[/yellow] Could not fetch remote benchmarks: {e}")
        remote_tasklists = []
    
    # Build unified list (deduplicated by name)
    all_tasklists: dict[str, TasklistInfo] = {}
    
    # Add conversion recipes first
    for item in available:
        key = item["name"].lower()
        all_tasklists[key] = TasklistInfo(
            name=item["name"],
            source="convertible",
            id=item.get("id", item["name"]),
            category=item.get("category"),
        )
    
    # Add remote tasklists (may override recipes with more info)
    for tl in remote_tasklists:
        key = tl.name.lower()
        if key not in all_tasklists:
            all_tasklists[key] = tl
    
    tasklists = list(all_tasklists.values())
    
    # Filter out already downloaded if requested
    if skip_existing:
        tasklists = [tl for tl in tasklists if not is_downloaded(tl.name)]
        if not tasklists:
            print("[green]All benchmarks are already downloaded.[/]")
            return
    
    # Show summary and confirm
    print()
    print(f"[bold]Found {len(tasklists)} benchmark(s) to download.[/]")
    print()
    print("[yellow]Warning:[/] This may download several gigabytes of data.")
    print("[dim]Use --skip-existing to only download missing benchmarks.[/]")
    print()
    
    if not auto_confirm:
        answer = questionary.confirm(
            f"Download {len(tasklists)} benchmarks?",
            default=False,  # Default to No since it's a big operation
        ).ask()
        
        if answer is None:
            # User cancelled (Ctrl+C)
            raise SystemExit(130)
        
        if not answer:
            print("[dim]Download cancelled.[/]")
            return
    
    # Download each tasklist
    print()
    succeeded = 0
    failed = 0
    skipped = 0
    
    for i, tl in enumerate(tasklists, 1):
        prefix = f"[{i}/{len(tasklists)}]"
        
        # Skip if already downloaded (double-check for non-skip-existing mode)
        if is_downloaded(tl.name):
            if not skip_existing:
                print(f"{prefix} [dim]Re-downloading {tl.name}...[/]")
            else:
                skipped += 1
                continue
        else:
            print(f"{prefix} Downloading {tl.name}...")
        
        try:
            if tl.source == "convertible":
                success = download_by_name(tl.name, skip_existing=skip_existing)
                if success:
                    succeeded += 1
                else:
                    skipped += 1
            elif tl.source in ("huggingface", "github", "gitlab"):
                import shutil
                import tempfile
                
                adapter = get_adapter(tl.source)
                folder_name = tl.id.replace("/", "--")
                dest = TASKLISTS_PATH / folder_name
                
                # Download to temp folder first, then move atomically
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_dest = Path(tmpdir) / folder_name
                    adapter.download(tl.id, tmp_dest)
                    
                    # Verify it has info.json before moving
                    if not (tmp_dest / "info.json").exists():
                        raise RuntimeError("Download incomplete: missing info.json")
                    
                    # Remove existing destination if any, then move
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.move(str(tmp_dest), str(dest))
                
                succeeded += 1
            else:
                print(f"  [yellow]Skipped (unknown source: {tl.source})[/]")
                skipped += 1
        except Exception as e:
            print(f"  [red]Failed: {e}[/]")
            failed += 1
    
    # Summary
    print()
    print(f"[bold]Download complete:[/]")
    print(f"  [green]✓ {succeeded} succeeded[/]")
    if skipped:
        print(f"  [dim]⏭ {skipped} skipped[/]")
    if failed:
        print(f"  [red]✗ {failed} failed[/]")


@click.command()
@click.argument("name", required=False)
@click.option("--all", "download_all", is_flag=True, help="Download all available benchmarks.")
@click.option("--skip-existing", is_flag=True, help="Skip benchmarks already downloaded.")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompts.")
def download(name: str | None, download_all: bool, skip_existing: bool, yes: bool) -> None:
    """Download a benchmark to local cache.

    NAME is the benchmark name (e.g., "MMLU", "GPQA Diamond") or a full
    identifier (e.g., "org/dataset"). Use 'palace list' to see available
    benchmarks.
    
    \b
    Examples:
        palace download MMLU
        palace download "GPQA Diamond"
        palace download altiema/my-benchmark
        palace download --all --skip-existing
        palace download --all -y
    """
    import questionary
    
    # Handle --all flag
    if download_all:
        _download_all_tasklists(skip_existing=skip_existing, auto_confirm=yes)
        return
    
    # NAME is required if --all is not specified
    if not name:
        raise click.UsageError("Missing argument 'NAME'.")
    
    ref = name  # Use 'ref' internally for compatibility with _find_tasklist
    # Check if already exists locally
    if skip_existing and is_downloaded(ref):
        print(f"[dim]Skipping {ref} (already downloaded)[/]")
        return
    
    if is_downloaded(ref):
        print(f"[yellow]Note:[/] {ref} already exists locally. Re-downloading...")
    
    # Find the tasklist
    tasklist = _find_tasklist(ref)
    
    if not tasklist:
        print(f"[red]Unknown tasklist: {ref}[/]")
        print(f"[dim]Run 'palace list' to see available tasklists.[/]")
        return
    
    # Download based on source type
    start_time = __import__('time').time()
    print(f"Downloading [bold]{tasklist.name}[/]...")
    
    try:
        if tasklist.source == "convertible":
            # Use legacy download system for conversion recipes
            success = download_by_name(tasklist.name)
            elapsed = __import__('time').time() - start_time
            if success:
                print(f"({elapsed:.1f}s)  [green]✓[/] Downloaded {tasklist.name}")
            else:
                print(f"({elapsed:.1f}s)  [yellow]⏭[/] Skipped {tasklist.name}")
                
        elif tasklist.source in ("huggingface", "github", "gitlab"):
            # Use git adapter to download
            # Store by full ID to avoid naming collisions (org/name -> org--name folder)
            import shutil
            import tempfile
            
            adapter = get_adapter(tasklist.source)
            folder_name = tasklist.id.replace("/", "--")
            dest = TASKLISTS_PATH / folder_name
            
            # Download to temp folder first, then move atomically
            # This ensures only complete downloads appear in the cache
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_dest = Path(tmpdir) / folder_name
                adapter.download(tasklist.id, tmp_dest)
                
                # Verify it has info.json before moving
                if not (tmp_dest / "info.json").exists():
                    raise RuntimeError("Download incomplete: missing info.json")
                
                # Remove existing destination if any, then move
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(tmp_dest), str(dest))
            
            elapsed = __import__('time').time() - start_time
            print(f"({elapsed:.1f}s)  [green]✓[/] Downloaded {tasklist.name}")
            
        else:
            print(f"[red]Cannot download from source: {tasklist.source}[/]")
            return
            
    except Exception as e:
        elapsed = __import__('time').time() - start_time
        print(f"({elapsed:.1f}s)  [red]✗[/] Download failed: {e}")
        raise SystemExit(1)
