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

"""Deprecated: the legacy interactive CLI was removed.

Use the unified 'palace' command instead (palace.cli). The deprecated
'palace-cli' entrypoint shows a deprecation warning and exits.
"""

from palace.utils.printing import print


def main():
    print("""[yellow]╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║  ⚠️  REMOVED                                                              ║
║                                                                          ║
║  The legacy interactive CLI has been removed.                            ║
║                                                                          ║
║  Please use the new unified 'palace' command instead.                    ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝[/yellow]""")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
