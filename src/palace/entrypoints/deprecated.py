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

"""Deprecation wrappers for old CLI entrypoints.

These wrappers display a deprecation warning then invoke the legacy behavior.
Users should migrate to the new unified 'palace' command.
"""

import sys

from palace.utils.printing import print

_DEPRECATION_BANNER = """
[yellow]╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║  ⚠️  DEPRECATION WARNING                                                  ║
║                                                                          ║
║  This command is deprecated and will be removed in a future release.     ║
║                                                                          ║
║  Please use the new unified 'palace' command instead:                    ║
║                                                                          ║
║    {new_command:<64} ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝[/yellow]
"""


def _show_deprecation_warning(old_cmd: str, new_cmd: str) -> None:
    """Display deprecation warning banner."""
    print(_DEPRECATION_BANNER.format(new_command=new_cmd))


def palace_cli_deprecated() -> None:
    """Deprecated: Use 'palace' instead."""
    _show_deprecation_warning("palace-cli", "palace")

    # Import and run the legacy interactive CLI
    from palace.entrypoints.palace_cli import main
    main()


def palace_run_deprecated() -> None:
    """Deprecated: Use 'palace run' instead."""
    _show_deprecation_warning("palace-run", "palace run <benchmark> -m <model>")

    # Import and run the legacy run CLI
    from palace.entrypoints.palace_run import run
    run()


def palace_download_deprecated() -> None:
    """Deprecated: Use 'palace download' instead."""
    _show_deprecation_warning("palace-download", "palace download <name>")

    # Import and run the legacy download CLI
    from palace.entrypoints.download.palace_download import main
    main()


def palace_mcpstart_deprecated() -> None:
    """Deprecated: MCP server functionality is being removed."""
    print("""
[yellow]╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║  ⚠️  DEPRECATION WARNING                                                  ║
║                                                                          ║
║  palace-mcpstart is deprecated and will be removed in a future release.  ║
║                                                                          ║
║  The MCP server functionality is being phased out.                       ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝[/yellow]
""")

    # Check if the old mcpstart module exists
    try:
        from palace.entrypoints.palace_mcpstart import main
        main()
    except ImportError:
        print("[red]Error: palace-mcpstart module not found.[/red]")
        sys.exit(1)
