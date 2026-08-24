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

"""Configuration commands: config, adapters, version."""

from importlib.metadata import version as pkg_version

import click
import yaml

from palace.utils.config import (
    CONFIG_FILE,
    CONFIG_TO_ENV,
    VALID_KEYS,
    delete_config_value,
    get_all_config,
    set_config_value,
)
from palace.utils.paths import (
    BUNDLED_IO_ADAPTERS_FILE,
    IO_ADAPTERS_FILE,
    RESULTS_PATH,
    TASKLISTS_PATH,
    USER_DIR,
)
from palace.utils.printing import print

# Display order for config keys (used in both config and env subcommands)
DISPLAY_ORDER = [
    "url",
    "key",
    "judge_url",
    "judge_key",
    "judge_model",
    "concurrency",
    "huggingface_token",
    "github_token",
    "gitlab_token",
    "vivarium_url",
]

# Keys that should be masked in output
SENSITIVE_KEYS = {"key", "judge_key", "huggingface_token", "github_token", "gitlab_token"}


def _mask_sensitive(key: str, value: str | None) -> str:
    """Mask sensitive values like keys and tokens."""
    if value is None:
        return "[dim]not set[/dim]"
    if key in SENSITIVE_KEYS:
        return "***"
    return value


def _validate_key(key: str) -> None:
    """Validate that key is a valid config key, exit if not."""
    if key not in VALID_KEYS:
        print(f"[red]Error:[/red] Invalid key: {key}")
        print(f"[dim]Valid keys: {', '.join(sorted(VALID_KEYS))}[/dim]")
        raise SystemExit(1)


@click.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Show or manage configuration.

    Without a subcommand, shows current configuration.
    Use 'palace config set' to save settings.

    \b
    Examples:
        palace config                    Show current config
        palace config set url <url>      Set API URL
        palace config set key <key>      Set API key
        palace config get url            Get a specific value
        palace config unset url          Remove a value
    """
    if ctx.invoked_subcommand is None:
        _show_config()


def _show_config() -> None:
    """Show current configuration."""
    print("[bold]Palace Configuration[/bold]\n")

    # Paths
    print("[bold]Paths:[/bold]")
    print(f"  Config: {CONFIG_FILE}")
    print(f"  Cache: {USER_DIR}")
    print(f"  Tasklists: {TASKLISTS_PATH}")
    print(f"  Results: {RESULTS_PATH}")

    # Configuration values
    print("\n[bold]Settings:[/bold]")

    all_config = get_all_config()

    for key in DISPLAY_ORDER:
        info = all_config.get(key, {"value": None, "source": None})
        value = _mask_sensitive(key, info["value"])
        source = info["source"]

        if source == "env":
            source_hint = " [dim](from env)[/dim]"
        elif source == "config":
            source_hint = ""
        else:
            source_hint = ""

        print(f"  {key}: {value}{source_hint}")

    # Stats
    print("\n[bold]Stats:[/bold]")

    # Count local tasklists
    tasklist_count = (
        sum(1 for d in TASKLISTS_PATH.iterdir() if d.is_dir() and (d / "info.json").exists())
        if TASKLISTS_PATH.exists()
        else 0
    )
    print(f"  Local tasklists: {tasklist_count}")

    # Count results
    result_count = sum(1 for _ in RESULTS_PATH.rglob("*.jsonl")) if RESULTS_PATH.exists() else 0
    print(f"  Result files: {result_count}")

    # Hint if not configured
    if not all_config["url"]["value"] and not all_config["key"]["value"]:
        print("\n[yellow]Not configured yet.[/yellow]")
        print("[dim]Run 'palace config set url <url>' and 'palace config set key <key>' to get started.[/dim]")


@config.command()
@click.argument("key")
@click.argument("value")
def set(key: str, value: str) -> None:
    """Set a configuration value.

    \b
    Available keys:
        url              API endpoint URL (for agent model)
        key              API key (for agent model)
        judge_url        API endpoint URL for judge (defaults to url)
        judge_key        API key for judge (defaults to key)
        judge_model      Model for judging answers
        concurrency      Number of parallel tasks
        huggingface_token  HuggingFace token
        github_token     GitHub token
        gitlab_token     GitLab token
        vivarium_url     Remote Vivarium URL

    \b
    Examples:
        palace config set url https://api.openai.com/v1
        palace config set key sk-...
        palace config set judge_model gpt-4o
    """
    try:
        set_config_value(key, value)
        masked = _mask_sensitive(key, value)
        print(f"[green]✓[/green] Set {key} = {masked}")
    except ValueError as e:
        print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@config.command()
@click.argument("key")
def get(key: str) -> None:
    """Get a configuration value.

    Shows the effective value (env var takes priority over config file).
    """
    _validate_key(key)

    all_config = get_all_config()
    info = all_config.get(key, {"value": None, "source": None})

    if info["value"]:
        masked = _mask_sensitive(key, info["value"])
        source = f" (from {info['source']})" if info["source"] else ""
        print(f"{masked}{source}")
    else:
        print("[dim]not set[/dim]")


@config.command()
@click.argument("key")
def unset(key: str) -> None:
    """Remove a configuration value from the config file.

    Note: This only removes from the config file. If the value is also
    set as an environment variable, that will still be used.
    """
    _validate_key(key)

    # Check if it's set via env var
    all_config = get_all_config()
    info = all_config.get(key, {"value": None, "source": None})
    is_from_env = info["source"] == "env"

    if delete_config_value(key):
        print(f"[green]✓[/green] Removed {key} from config file")
        if is_from_env:
            env_var = CONFIG_TO_ENV[key]
            print(f"[dim]Note: {key} is still set via env var {env_var}[/dim]")
    else:
        if is_from_env:
            env_var = CONFIG_TO_ENV[key]
            # Find .env file path (dotenv searches from cwd upward)
            from pathlib import Path

            cwd = Path.cwd()
            env_file = None
            for parent in [cwd] + list(cwd.parents):
                candidate = parent / ".env"
                if candidate.exists():
                    env_file = candidate
                    break

            print(f"[dim]{key} is set via env var {env_var}, not in config file[/dim]")
            if env_file:
                print(f"[dim]To unset: unset {env_var} and remove from {env_file}[/dim]")
            else:
                print(f"[dim]To unset: unset {env_var}[/dim]")
        else:
            print(f"[dim]{key} is not set (neither in config file nor env var)[/dim]")


@config.command("env")
def env_vars() -> None:
    """Show environment variable names for each config key.

    Useful for CI/Docker where you want to set config via env vars
    instead of the config file.
    """
    print("[bold]Environment Variables[/bold]\n")
    print("Set these instead of using 'palace config set' for CI/Docker:\n")

    for key in DISPLAY_ORDER:
        env_var = CONFIG_TO_ENV[key]
        print(f"  {key:20} → {env_var}")

    print("\n[dim]Priority: CLI flags > env vars > config file[/dim]")


@click.group(invoke_without_command=True)
@click.pass_context
def adapters(ctx: click.Context) -> None:
    """List and inspect I/O adapters.

    I/O adapters transform model input/output for specific models.
    Use 'palace adapters show <pattern>' to see adapter details.
    Use 'palace adapters match <model>' to see which adapter a model would use.
    """
    if ctx.invoked_subcommand is None:
        _list_adapters()


def _load_all_adapters() -> dict[str, dict]:
    """Load all adapters from bundled and user files."""
    all_adapters = {}

    if BUNDLED_IO_ADAPTERS_FILE.exists():
        try:
            bundled = yaml.safe_load(BUNDLED_IO_ADAPTERS_FILE.read_text()) or {}
            for p, config in bundled.items():
                all_adapters[p] = {"config": config, "source": "bundled"}
        except Exception:
            pass

    if IO_ADAPTERS_FILE.exists():
        try:
            user = yaml.safe_load(IO_ADAPTERS_FILE.read_text()) or {}
            for p, config in user.items():
                all_adapters[p] = {"config": config, "source": "user"}
        except Exception:
            pass

    return all_adapters


def _list_adapters() -> None:
    """List all adapters in compact format."""
    print("[bold]I/O Adapters[/bold]\n")

    # Bundled adapters
    bundled = {}
    if BUNDLED_IO_ADAPTERS_FILE.exists():
        try:
            bundled = yaml.safe_load(BUNDLED_IO_ADAPTERS_FILE.read_text()) or {}
        except Exception:
            pass

    print(f"[bold]Bundled ({len(bundled)}):[/bold]")
    if bundled:
        for pattern in bundled:
            print(f"  [cyan]{pattern}[/cyan]")
    else:
        print("  [dim]None[/dim]")

    # User adapters
    user = {}
    if IO_ADAPTERS_FILE.exists():
        try:
            user = yaml.safe_load(IO_ADAPTERS_FILE.read_text()) or {}
        except Exception:
            pass

    print(f"\n[bold]User ({len(user)}):[/bold]")
    if user:
        for pattern in user:
            print(f"  [green]{pattern}[/green]")
    else:
        print("  [dim]None[/dim]")
        print(f"  [dim]Create {IO_ADAPTERS_FILE} to add custom adapters[/dim]")

    if bundled or user:
        print("\n[dim]Commands:[/dim]")
        print("[dim]  palace adapters show <pattern>  - Show adapter details[/dim]")
        print("[dim]  palace adapters match <model>   - Find adapter for a model name[/dim]")


def _show_adapter_details(pattern: str, config: dict, source: str) -> None:
    """Display detailed info about an adapter."""
    source_color = "cyan" if source == "bundled" else "green"
    print(f"[{source_color}]{pattern}[/{source_color}] [{source}]\n")

    if "name" in config:
        print(f"  [bold]Name:[/bold] {config['name']}")

    if "input" in config:
        input_cfg = config["input"]
        print("  [bold]Input:[/bold]")
        for key, value in input_cfg.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            print(f"    {key}: {value_str}")

    if "output" in config:
        output_cfg = config["output"]
        print("  [bold]Output:[/bold]")
        for key, value in output_cfg.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            print(f"    {key}: {value_str}")


@adapters.command()
@click.argument("pattern")
def show(pattern: str) -> None:
    """Show details of a specific adapter.

    PATTERN is the adapter pattern (e.g., "*granite-guardian*").
    """
    all_adapters = _load_all_adapters()

    # Find exact match
    if pattern in all_adapters:
        adapter = all_adapters[pattern]
        _show_adapter_details(pattern, adapter["config"], adapter["source"])
        return

    # Try case-insensitive match
    for p in all_adapters:
        if p.lower() == pattern.lower():
            adapter = all_adapters[p]
            _show_adapter_details(p, adapter["config"], adapter["source"])
            return

    print(f"[red]Adapter pattern not found:[/red] {pattern}")
    print("[dim]Run 'palace adapters' to see available patterns[/dim]")
    print("[dim]Use 'palace adapters match <model>' to test model name matching[/dim]")


@adapters.command()
@click.argument("model")
def match(model: str) -> None:
    """Find which adapter matches a model name.

    MODEL is the model name to test (e.g., "granite-guardian-3.0-8b").
    """
    import fnmatch

    all_adapters = _load_all_adapters()

    # Find first matching adapter (user adapters take priority)
    # Sort so user adapters come before bundled
    sorted_adapters = sorted(all_adapters.items(), key=lambda x: (0 if x[1]["source"] == "user" else 1, x[0]))

    matched = None
    for pattern, adapter in sorted_adapters:
        if fnmatch.fnmatch(model, pattern):
            matched = (pattern, adapter)
            break

    print(f"[bold]Model:[/bold] {model}\n")

    if matched:
        pattern, adapter = matched
        print(f"[green]✓ Matches:[/green] {pattern}\n")
        _show_adapter_details(pattern, adapter["config"], adapter["source"])
    else:
        print("[dim]No adapter matches this model name.[/dim]")
        print("[dim]The model will use default I/O (no transformation).[/dim]")


@click.command("version")
def version_cmd() -> None:
    """Show package version."""
    try:
        ver = pkg_version("palace-eval")
    except Exception:
        ver = "unknown"
    click.echo(ver)
