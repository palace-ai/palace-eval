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

"""GitHub git adapter for tasklist discovery."""

import base64
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import requests

from palace.cli.git_adapters.base import GitAdapter, RateLimitError, TasklistInfo


class GitHubGitAdapter(GitAdapter):
    """Adapter for discovering tasklists from GitHub repos with palace-tasklist topic."""

    def __init__(self):
        from palace.utils.config import get_config_value

        self.token = get_config_value("github_token")
        self.base_url = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        """Get request headers with optional auth."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def _check_rate_limit(self, response: requests.Response) -> None:
        """Check if rate limited and raise appropriate error."""
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "0")
            reset_time = response.headers.get("X-RateLimit-Reset")

            if remaining == "0" or "rate limit" in response.text.lower():
                reset_int = int(reset_time) if reset_time else None
                raise RateLimitError(
                    "GitHub API rate limit exceeded. "
                    "Set GITHUB_TOKEN environment variable for higher limits (5000/hr vs 60/hr).\n"
                    "Create a token at: https://github.com/settings/tokens",
                    reset_time=reset_int,
                )

    def list_by_tag(self, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List all repos with the given topic.

        Args:
            tag: Topic to search for.

        Returns:
            List of discovered tasklists.
        """
        tasklists: list[TasklistInfo] = []

        try:
            response = requests.get(
                f"{self.base_url}/search/repositories",
                params={"q": f"topic:{tag}"},
                headers=self._headers(),
                timeout=30,
            )

            self._check_rate_limit(response)
            response.raise_for_status()

            data = response.json()
            for repo in data.get("items", []):
                tasklists.append(
                    TasklistInfo(
                        name=repo["name"],
                        source="github",
                        id=repo["full_name"],
                        description=repo.get("description"),
                        url=repo["html_url"],
                        official=(repo["owner"]["login"] == "palace-ai"),
                    )
                )
        except RateLimitError:
            raise
        except Exception:
            # Network or API errors - return empty list
            pass

        return tasklists

    def list_org(self, org: str, tag: str = "palace-tasklist") -> list[TasklistInfo]:
        """List repos in an org with the given topic.

        Args:
            org: Organization/user name.
            tag: Topic to filter by.

        Returns:
            List of discovered tasklists.
        """
        tasklists: list[TasklistInfo] = []

        try:
            response = requests.get(
                f"{self.base_url}/search/repositories",
                params={"q": f"topic:{tag} user:{org}"},
                headers=self._headers(),
                timeout=30,
            )

            self._check_rate_limit(response)
            response.raise_for_status()

            data = response.json()
            for repo in data.get("items", []):
                tasklists.append(
                    TasklistInfo(
                        name=repo["name"],
                        source="github",
                        id=repo["full_name"],
                        official=(org == "palace-ai"),
                        description=repo.get("description"),
                        url=repo["html_url"],
                    )
                )
        except RateLimitError:
            raise
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
            ValueError: If the repository doesn't exist.
        """
        try:
            response = requests.get(
                f"{self.base_url}/repos/{identifier}/contents/info.json",
                headers=self._headers(),
                timeout=30,
            )

            self._check_rate_limit(response)

            if response.status_code == 404:
                raise FileNotFoundError(f"info.json not found in {identifier}")

            response.raise_for_status()

            data = response.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content)

        except RateLimitError:
            raise
        except FileNotFoundError:
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Repository not found: {identifier}")
            raise

    def download(self, identifier: str, dest: Path) -> None:
        """Download a complete tasklist via archive.

        Args:
            identifier: Full identifier (e.g., "palace-ai/my-benchmark").
            dest: Destination directory.

        Raises:
            ValueError: If the repository doesn't exist.
        """
        dest.mkdir(parents=True, exist_ok=True)

        try:
            # Get default branch
            response = requests.get(
                f"{self.base_url}/repos/{identifier}",
                headers=self._headers(),
                timeout=30,
            )

            self._check_rate_limit(response)
            response.raise_for_status()

            default_branch = response.json().get("default_branch", "main")

            # Download archive
            archive_url = f"https://github.com/{identifier}/archive/refs/heads/{default_branch}.zip"

            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = Path(tmpdir) / "repo.zip"

                # Download zip
                with requests.get(archive_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)

                # Extract
                shutil.unpack_archive(zip_path, tmpdir)

                # Find extracted directory (usually repo-name-branch)
                extracted = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
                if extracted:
                    # Copy contents to dest
                    for item in extracted[0].iterdir():
                        if item.is_file():
                            shutil.copy2(item, dest / item.name)
                        else:
                            shutil.copytree(item, dest / item.name, dirs_exist_ok=True)

        except RateLimitError:
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Repository not found: {identifier}")
            raise

    def file_exists(self, identifier: str, path: str) -> bool:
        """Check if a file exists in the repo.

        Args:
            identifier: Full identifier (e.g., "palace-ai/my-benchmark").
            path: Path within the repo.

        Returns:
            True if file exists.
        """
        try:
            response = requests.get(
                f"{self.base_url}/repos/{identifier}/contents/{path}",
                headers=self._headers(),
                timeout=30,
            )
            return response.status_code == 200
        except Exception:
            return False
