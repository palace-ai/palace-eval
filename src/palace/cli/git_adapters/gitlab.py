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

"""GitLab git adapter for tasklist discovery."""

import base64
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

from palace.cli.git_adapters.base import GitAdapter, TasklistInfo


class GitLabGitAdapter(GitAdapter):
    """Adapter for discovering tasklists from GitLab repos with palace-tasklist topic."""

    def __init__(self, base_url: str = "https://gitlab.com"):
        from palace.utils.config import get_config_value
        self.token = get_config_value("gitlab_token")
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v4"

    def _headers(self) -> dict[str, str]:
        """Get request headers with optional auth."""
        headers = {"Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        return headers

    def list_by_tag(self, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List all projects with the given topic.

        Args:
            tag: Topic to search for.

        Returns:
            List of discovered tasklists.
        """
        tasklists: list[TasklistInfo] = []

        try:
            response = requests.get(
                f"{self.api_url}/projects",
                params={
                    "topic": tag,
                    "visibility": "public",
                    "per_page": 100,
                },
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()

            for project in response.json():
                tasklists.append(
                    TasklistInfo(
                        name=project["name"],
                        source="gitlab",
                        id=project["path_with_namespace"],
                        description=project.get("description"),
                        url=project["web_url"],
                        official=(project["namespace"]["path"] == "palace-ai"),
                    )
                )
        except Exception:
            # Network or API errors - return empty list
            pass

        return tasklists

    def list_org(self, org: str, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List projects in a group/user with the given topic.

        Args:
            org: Group/user name.
            tag: Topic to filter by.

        Returns:
            List of discovered tasklists.
        """
        tasklists: list[TasklistInfo] = []

        try:
            # Try as group first
            response = requests.get(
                f"{self.api_url}/groups/{quote_plus(org)}/projects",
                params={
                    "topic": tag,
                    "per_page": 100,
                },
                headers=self._headers(),
                timeout=30,
            )

            if response.status_code == 404:
                # Try as user
                response = requests.get(
                    f"{self.api_url}/users/{quote_plus(org)}/projects",
                    params={
                        "per_page": 100,
                    },
                    headers=self._headers(),
                    timeout=30,
                )

            response.raise_for_status()

            for project in response.json():
                # Filter by topic if user endpoint (doesn't support topic param)
                topics = project.get("topics", []) or project.get("tag_list", [])
                if tag not in topics:
                    continue

                tasklists.append(
                    TasklistInfo(
                        name=project["name"],
                        source="gitlab",
                        id=project["path_with_namespace"],
                        official=(org == "palace-ai"),
                        description=project.get("description"),
                        url=project["web_url"],
                    )
                )
        except Exception:
            # Network or API errors - return empty list
            pass

        return tasklists

    def get_info(self, identifier: str) -> dict[str, Any]:
        """Fetch info.json metadata for a tasklist.

        Args:
            identifier: Full identifier (e.g., "palace-ai/my-benchmark").

        Returns:
            Parsed info.json contents.

        Raises:
            FileNotFoundError: If info.json doesn't exist.
            ValueError: If the project doesn't exist.
        """
        encoded_id = quote_plus(identifier)

        try:
            response = requests.get(
                f"{self.api_url}/projects/{encoded_id}/repository/files/info.json",
                params={"ref": "main"},
                headers=self._headers(),
                timeout=30,
            )

            if response.status_code == 404:
                # Try master branch
                response = requests.get(
                    f"{self.api_url}/projects/{encoded_id}/repository/files/info.json",
                    params={"ref": "master"},
                    headers=self._headers(),
                    timeout=30,
                )

            if response.status_code == 404:
                raise FileNotFoundError(f"info.json not found in {identifier}")

            response.raise_for_status()

            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content)

        except FileNotFoundError:
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Project not found: {identifier}")
            raise

    def download(self, identifier: str, dest: Path) -> None:
        """Download a complete tasklist via archive.

        Args:
            identifier: Full identifier (e.g., "palace-ai/my-benchmark").
            dest: Destination directory.

        Raises:
            ValueError: If the project doesn't exist.
        """
        dest.mkdir(parents=True, exist_ok=True)
        encoded_id = quote_plus(identifier)

        try:
            # Download archive
            archive_url = f"{self.api_url}/projects/{encoded_id}/repository/archive.zip"

            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = Path(tmpdir) / "repo.zip"

                with requests.get(
                    archive_url,
                    headers=self._headers(),
                    stream=True,
                    timeout=60,
                ) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                # Extract
                shutil.unpack_archive(zip_path, tmpdir)

                # Find extracted directory
                extracted = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
                if extracted:
                    for item in extracted[0].iterdir():
                        if item.is_file():
                            shutil.copy2(item, dest / item.name)
                        else:
                            shutil.copytree(item, dest / item.name, dirs_exist_ok=True)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Project not found: {identifier}")
            raise

    def file_exists(self, identifier: str, path: str) -> bool:
        """Check if a file exists in the project.

        Args:
            identifier: Full identifier (e.g., "palace-ai/my-benchmark").
            path: Path within the repo.

        Returns:
            True if file exists.
        """
        encoded_id = quote_plus(identifier)
        encoded_path = quote_plus(path)

        try:
            response = requests.head(
                f"{self.api_url}/projects/{encoded_id}/repository/files/{encoded_path}",
                params={"ref": "main"},
                headers=self._headers(),
                timeout=30,
            )
            return response.status_code == 200
        except Exception:
            return False
