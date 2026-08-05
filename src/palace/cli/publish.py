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

"""Publish command: palace publish."""

import sys
from pathlib import Path

import click
import questionary

from palace.cli.validation import Validator
from palace.download import resolve_local_path
from palace.utils.printing import print


@click.command()
@click.argument("name")
@click.option("--repo", "-r", default=None, help="Repository name (default: tasklist name).")
@click.option("--org", "-o", default=None, help="Organization/username (default: your HF username).")
@click.option("--token", "-t", default=None, help="HuggingFace token (default: use logged-in token).")
@click.option("--private", is_flag=True, help="Create a private repository.")
@click.option("--dry-run", is_flag=True, help="Show what would be done without uploading.")
def publish(name: str, repo: str | None, org: str | None, token: str | None, private: bool, dry_run: bool) -> None:
    """Publish a benchmark to HuggingFace.

    NAME is the benchmark name (e.g., "my-benchmark") or path to a tasklist directory.

    This command will:
    1. Validate the tasklist
    2. Create a HuggingFace dataset repository (if it doesn't exist)
    3. Upload all files
    4. Add the 'palace-tasklist' tag for discoverability

    \b
    Examples:
        palace publish my-benchmark
        palace publish ./path/to/tasklist
        palace publish my-benchmark --org palace-ai
        palace publish my-benchmark --org palace-ai --token hf_xxx
        palace publish my-benchmark --dry-run
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

    repo_name = repo or path.name

    print(f"[bold]Publishing:[/bold] {repo_name}\n")

    # Run validation first
    print("[dim]Running validation...[/dim]")
    validator = Validator()
    errors, warnings = validator.validate(path)

    if errors:
        print(f"\n[red]✗ Validation failed with {len(errors)} error(s)[/red]")
        for err in errors:
            print(f"  [red]•[/red] {err.message}")
        print(f"\n[dim]Run 'palace validate {path_or_name}' for details.[/dim]")
        sys.exit(1)

    if warnings:
        print(f"[yellow]⚠ {len(warnings)} warning(s) found (non-blocking)[/yellow]")
    else:
        print("[green]✓ Validation passed[/green]")

    # Check HuggingFace authentication
    print("\n[dim]Checking HuggingFace authentication...[/dim]")

    try:
        from huggingface_hub import HfApi, whoami

        # Use provided token or default
        api = HfApi(token=token) if token else HfApi()

        try:
            user_info = whoami(token=token) if token else whoami()
            username = user_info["name"]
            if token:
                print(f"[green]✓ Using provided token:[/green] {username}")
            else:
                print(f"[green]✓ Logged in as:[/green] {username}")
        except Exception:
            if token:
                print("[red]✗ Invalid token[/red]")
                print()
                print("The provided token is invalid or expired.")
                print("Get a new token at: [blue]https://huggingface.co/settings/tokens[/blue]")
            else:
                print("[red]✗ Not logged in to HuggingFace[/red]")
                print()
                print("Please login first:")
                print("  [dim]huggingface-cli login[/dim]")
                print("  or set HUGGINGFACE_TOKEN environment variable")
                print("  or use --token to provide a token")
            sys.exit(1)
    except ImportError:
        print("[red]Error: huggingface_hub not installed[/red]")
        sys.exit(1)

    # Determine repo ID
    namespace = org or username
    repo_id = f"{namespace}/{repo_name}"
    repo_url = f"https://huggingface.co/datasets/{repo_id}"

    # Check if publishing to a different org
    publishing_to_different_org = org and org != username

    # Show summary and confirm
    print()
    print("=" * 60)
    print("[bold yellow]⚠️  PUBLISH CONFIRMATION[/]")
    print("=" * 60)
    print()
    print(f"  [bold]Source:[/bold]      {path}")
    print(f"  [bold]Repository:[/bold]  {repo_id}")
    print(f"  [bold]URL:[/bold]         {repo_url}")
    print(f"  [bold]Visibility:[/bold]  {'Private' if private else 'Public'}")

    if publishing_to_different_org:
        print()
        print(f"  [yellow]Note:[/yellow] Publishing to organization '{org}' (not your personal account)")
        print("        You must have write access to this organization.")

    print()
    print("  This will:")
    print("    • Create a new HuggingFace dataset repository (if needed)")
    print("    • Upload all files from the tasklist directory")
    print("    • Add the 'palace-tasklist' tag for discoverability")
    print()

    if dry_run:
        print("[cyan]DRY RUN - No changes will be made[/cyan]")
        print()
        print("Files that would be uploaded:")
        for f in sorted(path.rglob("*")):
            if f.is_file():
                rel = f.relative_to(path)
                size = f.stat().st_size
                print(f"  {rel} ({_format_size(size)})")
        return

    print("[yellow]This action will make your benchmark publicly visible![/yellow]")
    print()

    confirm = questionary.confirm(
        "Proceed with publishing?",
        default=False,
    ).ask()

    if confirm is None or not confirm:
        print("[dim]Publishing cancelled.[/dim]")
        return

    # Create repository
    print()
    print("[dim]Creating repository...[/dim]")

    try:
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True,  # Don't fail if it already exists
        )
        print(f"[green]✓ Repository ready:[/green] {repo_id}")
    except Exception as e:
        print(f"[red]✗ Failed to create repository:[/red] {e}")
        sys.exit(1)

    # Upload files
    print("[dim]Uploading files...[/dim]")

    try:
        api.upload_folder(
            folder_path=str(path),
            repo_id=repo_id,
            repo_type="dataset",
            commit_message="Upload palace tasklist",
        )
        print("[green]✓ Files uploaded[/green]")
    except Exception as e:
        print(f"[red]✗ Upload failed:[/red] {e}")
        sys.exit(1)

    # Add palace-tasklist tag
    print("[dim]Adding palace-tasklist tag...[/dim]")

    try:
        # Get current metadata
        from huggingface_hub import DatasetCard, DatasetCardData

        try:
            card = DatasetCard.load(repo_id)
        except Exception:
            # No card exists, create one with tags initialized
            card = DatasetCard("")
            card.data = DatasetCardData(tags=[])

        # Ensure tags list exists
        if not hasattr(card.data, "tags") or card.data.tags is None:
            card.data.tags = []

        # Add tag if not present
        if "palace-tasklist" not in card.data.tags:
            card.data.tags.append("palace-tasklist")

        # Push updated card
        card.push_to_hub(repo_id, repo_type="dataset", token=token)
        print("[green]✓ Tag added[/green]")
    except Exception as e:
        print(f"[yellow]⚠ Could not add tag automatically:[/yellow] {e}")
        print("  Please add the 'palace-tasklist' tag manually in the dataset settings.")

    # Success!
    print()
    print("=" * 60)
    print("[bold green]✓ PUBLISHED SUCCESSFULLY[/]")
    print("=" * 60)
    print()
    print("  Your benchmark is now available at:")
    print(f"  [blue]{repo_url}[/blue]")
    print()
    print("  It will appear in 'palace list' once the tag is indexed.")
    print()


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
