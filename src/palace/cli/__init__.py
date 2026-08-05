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

"""Palace CLI - Unified command-line interface for LLM benchmark evaluation."""

import click

from importlib.metadata import version


def get_version() -> str:
    """Get package version."""
    try:
        return version("palace-eval")
    except Exception:
        return "unknown"


@click.group(invoke_without_command=True, add_help_option=False)
@click.pass_context
def palace(ctx: click.Context) -> None:
    """Palace - LLM Benchmark Evaluation Toolkit.

    A unified CLI for discovering, downloading, running, and publishing
    LLM benchmarks.

    \b
    Quick start:
      palace list              List available benchmarks
      palace download MMLU     Download a benchmark
      palace run MMLU          Run evaluation on a benchmark
      palace init my-bench     Create a new benchmark

    \b
    Documentation: https://palace.pages.code.europa.eu/palace-eval

    \b
    Run 'palace help' for usage information.
    Run 'palace version' to see the installed version.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@palace.command()
@click.pass_context
def help(ctx: click.Context) -> None:
    """Show this help information."""
    click.echo(ctx.parent.get_help())


# Import and register subcommands
# These are imported lazily to avoid slow startup
def _register_commands() -> None:
    """Register all subcommands."""
    from palace.cli.discovery import list_cmd, search, info
    from palace.cli.sources_cmd import sources
    from palace.cli.download_cmd import download
    from palace.cli.local import local
    from palace.cli.run import run
    from palace.cli.results import results
    from palace.cli.init_cmd import init
    from palace.cli.validate import validate
    from palace.cli.publish import publish
    from palace.cli.config import config, adapters, version_cmd

    palace.add_command(list_cmd, name="list")
    palace.add_command(search)
    palace.add_command(info)
    palace.add_command(sources)
    palace.add_command(download)
    palace.add_command(local)
    palace.add_command(run)
    palace.add_command(results)
    palace.add_command(init)
    palace.add_command(validate)
    palace.add_command(publish)
    palace.add_command(config)
    palace.add_command(adapters)
    palace.add_command(version_cmd, name="version")


# Register commands on import
_register_commands()


def main() -> None:
    """Entry point for the palace CLI."""
    palace()


if __name__ == "__main__":
    main()
