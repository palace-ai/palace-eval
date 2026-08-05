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

"""Palace download module - Public API for downloading tasklists.

This module provides programmatic access to download functionality,
suitable for use by CLI and external tools like palace-gradin.

Examples:
    # Download a specific tasklist by name
    from palace.download import download_by_name
    download_by_name("MMLU")

    # List available tasklists that can be downloaded
    from palace.download import list_downloadable
    for item in list_downloadable():
        print(f"{item['name']} - {item.get('category', 'Unknown')}")

    # Download with progress callback
    from palace.download import download_by_name, DownloadEvent
    def on_progress(event: DownloadEvent):
        print(f"{event.name}: {event.status}")
    download_by_name("MMLU", on_progress=on_progress)
"""

from pathlib import Path
from typing import Callable

# Re-export from the existing download module
from palace.entrypoints.download.palace_download import (
    DownloadEvent,
    download_all,
)
from palace.entrypoints.download.palace_download import (
    download_tasklist as _download_tasklist_raw,
)
from palace.entrypoints.download.palace_download import (
    list_downloads as _list_downloads,
)
from palace.utils.paths import TASKLISTS_PATH


def list_downloadable(skip_existing: bool = False) -> list[dict]:
    """List tasklists available for download.

    Returns information about tasklists that can be downloaded, including
    both conversion recipes (public HuggingFace datasets) and native
    palace tasklists.

    Args:
        skip_existing: If True, exclude tasklists already downloaded locally.

    Returns:
        List of dicts with 'name', 'category', and other metadata.

    Example:
        >>> from palace.download import list_downloadable
        >>> for item in list_downloadable(skip_existing=True):
        ...     print(f"{item['name']}: {item.get('category', 'Unknown')}")
    """
    return _list_downloads(skip_existing=skip_existing)


def download_by_name(
    name: str,
    on_progress: Callable[[DownloadEvent], None] | None = None,
    skip_existing: bool = False,
) -> bool:
    """Download a tasklist by name.

    This function handles both:
    - Conversion recipes: HuggingFace datasets converted to palace format
    - Native palace tasklists: Direct downloads from palace-ai repositories

    Args:
        name: Name of the tasklist to download (e.g., "MMLU", "GPQA Diamond").
        on_progress: Optional callback for progress updates.
        skip_existing: If True, skip if already downloaded.

    Returns:
        True if download succeeded, False if skipped or failed.

    Raises:
        ValueError: If tasklist name is not found.

    Example:
        >>> from palace.download import download_by_name
        >>> download_by_name("MMLU")
        True
    """
    # Check if already exists
    dest_path = TASKLISTS_PATH / name
    if skip_existing and (dest_path / "info.json").exists():
        return False

    # Find in downloadable list
    all_items = _list_downloads(skip_existing=False, tasklists=[name])

    if not all_items:
        raise ValueError(f"Tasklist not found: {name}")

    # Use download_all with single tasklist filter
    download_all(on_progress=on_progress, skip_existing=skip_existing, tasklists=[name])

    # Check if download succeeded
    return (dest_path / "info.json").exists()


def is_downloaded(name: str) -> bool:
    """Check if a tasklist is already downloaded locally.

    Args:
        name: Name or ID of the tasklist (e.g., "MMLU", "SWE-bench Verified", or "org/name").

    Returns:
        True if the tasklist exists and is complete.
    """
    return resolve_local_path(name) is not None


def get_local_path(name: str) -> Path | None:
    """Get the local path for a downloaded tasklist.

    Args:
        name: Name or ID of the tasklist (e.g., "MMLU" or "org/name").

    Returns:
        Path to the tasklist directory, or None if not downloaded.
    """
    path = resolve_local_path(name)
    return path if path else None


def resolve_local_path(identifier: str) -> Path | None:
    """Resolve a tasklist identifier (display name, folder name, or ID) to local path.

    This function handles all forms of tasklist identification:
    - Display name from info.json (e.g., "SWE-bench Verified")
    - Folder name (e.g., "SWE-bench-Verified")
    - ID with org (e.g., "palace-ai/swe-bench-verified")

    Args:
        identifier: Any form of tasklist identifier.

    Returns:
        Path to the tasklist directory if found and has info.json, None otherwise.

    Example:
        >>> from palace.download import resolve_local_path
        >>> path = resolve_local_path("SWE-bench Verified")
        >>> if path:
        ...     print(f"Found at: {path}")
    """
    import json

    identifier_lower = identifier.lower()

    # 1. Try exact folder match first (fastest)
    path = TASKLISTS_PATH / identifier
    if (path / "info.json").exists():
        return path

    # 2. Try org/name -> org--name folder format
    if "/" in identifier:
        folder_name = identifier.replace("/", "--")
        path = TASKLISTS_PATH / folder_name
        if (path / "info.json").exists():
            return path

    # 3. Try case-insensitive folder match
    if TASKLISTS_PATH.exists():
        for d in TASKLISTS_PATH.iterdir():
            if d.is_dir() and d.name.lower() == identifier_lower:
                if (d / "info.json").exists():
                    return d

    # 4. Try matching display name from info.json (handles spaces, etc.)
    if TASKLISTS_PATH.exists():
        for d in TASKLISTS_PATH.iterdir():
            if not d.is_dir():
                continue

            info_file = d / "info.json"
            if not info_file.exists():
                continue

            try:
                info = json.loads(info_file.read_text())
                display_name = info.get("name", "")
                if display_name.lower() == identifier_lower:
                    return d
            except (json.JSONDecodeError, OSError):
                continue

    return None


__all__ = [
    "DownloadEvent",
    "download_by_name",
    "download_all",
    "list_downloadable",
    "is_downloaded",
    "get_local_path",
    "resolve_local_path",
]
