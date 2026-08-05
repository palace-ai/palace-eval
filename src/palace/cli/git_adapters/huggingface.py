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

"""HuggingFace git adapter for tasklist discovery."""

import json
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

from palace.cli.git_adapters.base import GitAdapter, TasklistInfo


class HuggingFaceGitAdapter(GitAdapter):
    """Adapter for discovering tasklists from HuggingFace Hub."""

    def __init__(self):
        self.api = HfApi()

    def list_by_tag(self, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List all datasets with the given tag.

        Args:
            tag: Tag to search for.

        Returns:
            List of discovered tasklists.
        """
        tasklists: list[TasklistInfo] = []

        try:
            datasets = list(self.api.list_datasets(filter=tag))
            for ds in datasets:
                tasklists.append(
                    TasklistInfo(
                        name=ds.id.split("/")[-1],
                        source="huggingface",
                        id=ds.id,
                        description=getattr(ds, "description", None),
                        url=f"https://huggingface.co/datasets/{ds.id}",
                    )
                )
        except Exception:
            # Network or API errors - return empty list
            pass

        return tasklists

    def list_org(self, org: str, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List datasets in an org with the given tag.

        Args:
            org: Organization/user name.
            tag: Tag to filter by.

        Returns:
            List of discovered tasklists.
        """
        tasklists: list[TasklistInfo] = []

        try:
            datasets = list(self.api.list_datasets(author=org, filter=tag))
            for ds in datasets:
                tasklists.append(
                    TasklistInfo(
                        name=ds.id.split("/")[-1],
                        source="huggingface",
                        id=ds.id,
                        official=(org == "palace-ai"),
                        description=getattr(ds, "description", None),
                        url=f"https://huggingface.co/datasets/{ds.id}",
                    )
                )
        except Exception:
            # Network or API errors - return empty list
            pass

        return tasklists

    def get_info(self, identifier: str) -> dict[str, Any]:
        """Fetch info.json metadata for a tasklist.

        Args:
            identifier: Full identifier (e.g., "palace-ai/MMLU").

        Returns:
            Parsed info.json contents.

        Raises:
            FileNotFoundError: If info.json doesn't exist.
            ValueError: If the repository doesn't exist.
        """
        try:
            info_path = hf_hub_download(
                repo_id=identifier,
                filename="info.json",
                repo_type="dataset",
            )
            return json.loads(Path(info_path).read_text())
        except EntryNotFoundError:
            raise FileNotFoundError(f"info.json not found in {identifier}")
        except RepositoryNotFoundError:
            raise ValueError(f"Repository not found: {identifier}")

    def download(self, identifier: str, dest: Path) -> None:
        """Download a complete tasklist.

        Args:
            identifier: Full identifier (e.g., "palace-ai/MMLU").
            dest: Destination directory.

        Raises:
            ValueError: If the repository doesn't exist.
        """
        from huggingface_hub import snapshot_download

        dest.mkdir(parents=True, exist_ok=True)

        try:
            # Use snapshot_download which handles the full repo download
            snapshot_download(
                repo_id=identifier,
                repo_type="dataset",
                local_dir=dest,
            )
        except RepositoryNotFoundError:
            raise ValueError(f"Repository not found: {identifier}")

    def file_exists(self, identifier: str, path: str) -> bool:
        """Check if a file exists in the dataset.

        Args:
            identifier: Full identifier (e.g., "palace-ai/MMLU").
            path: Path within the repo.

        Returns:
            True if file exists.
        """
        try:
            self.api.hf_hub_url(
                repo_id=identifier,
                filename=path,
                repo_type="dataset",
            )
            return True
        except Exception:
            return False
