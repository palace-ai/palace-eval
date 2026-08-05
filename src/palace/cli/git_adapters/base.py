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

"""Base protocol for git hosting platform adapters.

Note: These are 'git adapters' for fetching from git hosts (HuggingFace, GitHub, GitLab),
distinct from 'I/O adapters' which transform model input/output.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TasklistInfo:
    """Metadata about a discoverable tasklist."""

    name: str
    source: str  # "huggingface", "github", "gitlab", "local", "convertible"
    id: str  # Full identifier (e.g., "palace-ai/MMLU", "owner/repo")
    official: bool = False  # From palace-ai org
    description: str | None = None
    category: str | None = None
    task_type: str | None = None
    task_count: int | None = None
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def display_source(self) -> str:
        """Return display string for source type."""
        source_map = {
            "huggingface": "[HF]",
            "github": "[GitHub]",
            "gitlab": "[GitLab]",
            "local": "[local]",
            "convertible": "[convertible]",
        }
        return source_map.get(self.source, f"[{self.source}]")


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str, reset_time: int | None = None):
        super().__init__(message)
        self.reset_time = reset_time


class GitAdapter(ABC):
    """Abstract base class for git hosting platform adapters.

    Implementations must provide methods to:
    - List repositories/datasets with the palace-tasklist tag
    - Read metadata files (info.json)
    - Download complete tasklists
    """

    @abstractmethod
    def list_by_tag(self, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List all repos/datasets with the given tag.

        Args:
            tag: Tag/topic to search for.

        Returns:
            List of discovered tasklists.
        """
        ...

    @abstractmethod
    def list_org(self, org: str, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List repos/datasets in an org with the given tag.

        Args:
            org: Organization/user name.
            tag: Tag/topic to filter by.

        Returns:
            List of discovered tasklists.
        """
        ...

    @abstractmethod
    def get_info(self, identifier: str) -> dict[str, Any]:
        """Fetch info.json metadata for a tasklist without full download.

        Args:
            identifier: Full identifier (e.g., "palace-ai/MMLU").

        Returns:
            Parsed info.json contents.
        """
        ...

    @abstractmethod
    def download(self, identifier: str, dest: Path) -> None:
        """Download a complete tasklist to the destination.

        Args:
            identifier: Full identifier (e.g., "palace-ai/MMLU").
            dest: Destination directory.
        """
        ...

    def file_exists(self, identifier: str, path: str) -> bool:
        """Check if a file exists in the repo.

        Args:
            identifier: Full identifier (e.g., "palace-ai/MMLU").
            path: Path within the repo.

        Returns:
            True if file exists.
        """
        try:
            self.get_info(identifier)
            return True
        except Exception:
            return False
