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

"""Git adapter registry and auto-detection."""

from pathlib import Path
from urllib.parse import urlparse

from palace.cli.git_adapters.base import GitAdapter, TasklistInfo, RateLimitError


def detect_adapter(url: str) -> tuple[str, str | None, dict]:
    """Auto-detect source type and extract org/identifier from URL.

    Args:
        url: URL or path to detect.

    Returns:
        Tuple of (adapter_type, org_or_identifier, extra_info).
        adapter_type is one of: "huggingface", "github", "gitlab", "local"
        extra_info contains additional parsed data (collection_slug, collection_title, repo, etc.)

    Examples:
        >>> detect_adapter("https://huggingface.co/palace-ai")
        ("huggingface", "palace-ai", {})
        >>> detect_adapter("https://huggingface.co/datasets/palace-ai/MMLU")
        ("huggingface", "palace-ai", {"dataset": "palace-ai/MMLU"})
        >>> detect_adapter("https://huggingface.co/collections/jrc-ai/palace-abc123")
        ("huggingface", "jrc-ai", {"collection_slug": "jrc-ai/palace-abc123"})
        >>> detect_adapter("https://huggingface.co/collections/jrc-ai/palace")
        ("huggingface", "jrc-ai", {"collection_title": "palace"})
        >>> detect_adapter("https://github.com/palace-ai")
        ("github", "palace-ai", {})
        >>> detect_adapter("/path/to/tasklists")
        ("local", "/path/to/tasklists", {})
    """
    # Check if it's a local path
    if Path(url).exists():
        return "local", url, {}

    # Handle bare domain URLs without scheme
    if not url.startswith(("http://", "https://", "/")):
        url = "https://" + url

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    extra: dict = {}

    if "huggingface.co" in host or "hf.co" in host:
        # HuggingFace URL patterns:
        # - https://huggingface.co/org-name (org page)
        # - https://huggingface.co/datasets/org/dataset-name (dataset page)
        # - https://huggingface.co/collections/org/collection-slug (collection page with full slug)
        # - https://huggingface.co/collections/org/collection-title (collection page with title only)
        
        if not path_parts:
            return "huggingface", None, {}
        
        if path_parts[0] == "datasets":
            # Dataset URL: https://huggingface.co/datasets/org/dataset-name
            if len(path_parts) >= 3:
                org = path_parts[1]
                dataset_id = f"{path_parts[1]}/{path_parts[2]}"
                extra["dataset"] = dataset_id
                return "huggingface", org, extra
            elif len(path_parts) >= 2:
                org = path_parts[1]
                return "huggingface", org, extra
            return "huggingface", None, extra
        
        if path_parts[0] == "collections":
            # Collection URL: https://huggingface.co/collections/org/collection-name[-uniqueid]
            if len(path_parts) >= 3:
                org = path_parts[1]
                collection_part = path_parts[2]
                # Check if it looks like a full slug (has hex ID suffix)
                # Full slugs look like: "palace-698071045baae6945f7757e2"
                if len(collection_part) > 24 and collection_part[-24:].replace('-', '').isalnum():
                    # Looks like a full slug
                    extra["collection_slug"] = f"{org}/{collection_part}"
                else:
                    # Just a title, needs lookup
                    extra["collection_title"] = collection_part
                return "huggingface", org, extra
            elif len(path_parts) >= 2:
                org = path_parts[1]
                return "huggingface", org, extra
            return "huggingface", None, extra
        
        # Org URL: https://huggingface.co/org-name
        org = path_parts[0]
        return "huggingface", org, extra

    if "github.com" in host:
        # GitHub: https://github.com/org or https://github.com/org/repo
        if not path_parts:
            return "github", None, {}
        org = path_parts[0]
        if len(path_parts) >= 2:
            extra["repo"] = f"{path_parts[0]}/{path_parts[1]}"
        return "github", org, extra

    if "gitlab" in host:
        # GitLab: https://gitlab.com/org or https://gitlab.com/org/repo
        if not path_parts:
            return "gitlab", None, {}
        org = path_parts[0]
        if len(path_parts) >= 2:
            extra["repo"] = f"{path_parts[0]}/{path_parts[1]}"
        return "gitlab", org, extra

    # Unknown URL type
    org = path_parts[0] if path_parts else None
    return "unknown", org, {}


def get_adapter(adapter_type: str) -> GitAdapter:
    """Get adapter instance by type.

    Args:
        adapter_type: One of "huggingface", "github", "gitlab", "local".

    Returns:
        Configured adapter instance.

    Raises:
        ValueError: If adapter type is unknown.
    """
    if adapter_type == "huggingface":
        from palace.cli.git_adapters.huggingface import HuggingFaceGitAdapter

        return HuggingFaceGitAdapter()
    elif adapter_type == "github":
        from palace.cli.git_adapters.github import GitHubGitAdapter

        return GitHubGitAdapter()
    elif adapter_type == "gitlab":
        from palace.cli.git_adapters.gitlab import GitLabGitAdapter

        return GitLabGitAdapter()
    elif adapter_type == "local":
        from palace.cli.git_adapters.local import LocalAdapter

        return LocalAdapter()
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")


__all__ = [
    "GitAdapter",
    "TasklistInfo",
    "RateLimitError",
    "detect_adapter",
    "get_adapter",
]
