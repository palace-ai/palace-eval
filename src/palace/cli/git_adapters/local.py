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

"""Local filesystem adapter for tasklist discovery."""

import json
import shutil
from pathlib import Path
from typing import Any

from palace.cli.git_adapters.base import GitAdapter, TasklistInfo
from palace.utils.paths import TASKLISTS_PATH


class LocalAdapter(GitAdapter):
    """Adapter for discovering locally downloaded tasklists."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or TASKLISTS_PATH

    def list_tasklists(self) -> list[TasklistInfo]:
        """List all local tasklists.

        Returns:
            List of local tasklists.
        """
        tasklists: list[TasklistInfo] = []

        if not self.base_path.exists():
            return tasklists

        for path in self.base_path.iterdir():
            if not path.is_dir():
                continue

            info_file = path / "info.json"

            # A directory is a palace tasklist if it contains info.json
            if not info_file.exists():
                continue

            # Determine the ID: if folder has double-dash, it's org--name format
            folder_name = path.name
            if "--" in folder_name:
                # org--name format (e.g., "altiema--my-benchmark")
                # Convert back to org/name for display
                parts = folder_name.split("--", 1)
                if len(parts) == 2:
                    display_id = f"{parts[0]}/{parts[1]}"
                else:
                    display_id = folder_name
            else:
                display_id = folder_name

            try:
                info = json.loads(info_file.read_text())
                tasklists.append(
                    TasklistInfo(
                        name=info.get("name", path.name),
                        source="local",
                        id=display_id,
                        description=info.get("description"),
                        category=info.get("category"),
                        task_type=info.get("task_type"),
                        extra={"path": str(path), "folder": folder_name},
                    )
                )
            except (json.JSONDecodeError, OSError):
                # Corrupted info.json, still list it
                tasklists.append(
                    TasklistInfo(
                        name=path.name,
                        source="local",
                        id=display_id,
                        extra={"path": str(path), "folder": folder_name},
                    )
                )

        return tasklists

    def list_by_tag(self, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List all local tasklists (tag is ignored for local).

        Args:
            tag: Ignored for local adapter.

        Returns:
            List of local tasklists.
        """
        return self.list_tasklists()

    def list_org(self, org: str, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List local tasklists (org is ignored for local).

        Args:
            org: Ignored for local adapter.
            tag: Ignored for local adapter.

        Returns:
            List of local tasklists.
        """
        return self.list_tasklists()

    def get_info(self, identifier: str) -> dict[str, Any]:
        """Get info.json for a local tasklist.

        Args:
            identifier: Tasklist name.

        Returns:
            Parsed info.json contents.

        Raises:
            FileNotFoundError: If tasklist or info.json doesn't exist.
        """
        path = self.base_path / identifier
        if not path.exists():
            raise FileNotFoundError(f"Tasklist not found: {identifier}")

        info_file = path / "info.json"
        if not info_file.exists():
            raise FileNotFoundError(f"info.json not found in {identifier}")

        return json.loads(info_file.read_text())

    def download(self, identifier: str, dest: Path) -> None:
        """Copy a local tasklist to destination (no-op if same path).

        Args:
            identifier: Tasklist name.
            dest: Destination directory.

        Raises:
            FileNotFoundError: If tasklist doesn't exist.
        """
        source = self.base_path / identifier
        if not source.exists():
            raise FileNotFoundError(f"Tasklist not found: {identifier}")

        if source.resolve() == dest.resolve():
            return  # Same path, nothing to do

        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, dest, dirs_exist_ok=True)

    def file_exists(self, identifier: str, path: str) -> bool:
        """Check if a file exists in a local tasklist.

        Args:
            identifier: Tasklist name.
            path: Path within the tasklist.

        Returns:
            True if file exists.
        """
        full_path = self.base_path / identifier / path
        return full_path.exists()

    def remove(self, name: str) -> bool:
        """Remove a local tasklist.

        Args:
            name: Tasklist name.

        Returns:
            True if removed, False if not found.
        """
        path = self.base_path / name
        if not path.exists():
            return False

        shutil.rmtree(path)
        return True
