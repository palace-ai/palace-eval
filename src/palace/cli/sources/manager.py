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

"""Source manager for aggregating tasklist sources."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from palace.cli.git_adapters import detect_adapter, get_adapter, TasklistInfo, RateLimitError
from palace.cli.sources.cache import SourceCache
from palace.utils.paths import CONFIG_DIR

SOURCES_FILE = CONFIG_DIR / "sources.yaml"

# Official organization on HuggingFace
OFFICIAL_ORG = "palace-ai"


@dataclass
class Source:
    """A configured source for tasklist discovery."""

    type: str  # "huggingface", "github", "gitlab", "local"
    url: str | None = None
    org: str | None = None
    tag: str = "palace-tasklist"
    official: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> str:
        """Generate unique cache key for this source."""
        collection_slug = self.extra.get("collection_slug") if self.extra else None
        if collection_slug:
            return f"{self.type}:collection:{collection_slug}"
        return f"{self.type}:{self.org or self.url or 'default'}:{self.tag}"


class SourceManager:
    """Aggregates and manages tasklist sources."""

    def __init__(self, sources_file: Path = SOURCES_FILE):
        self.sources_file = sources_file
        self.cache = SourceCache()
        self._user_sources: list[Source] = []
        self._load_user_sources()

    def _load_user_sources(self) -> None:
        """Load user-configured sources from YAML file."""
        if not self.sources_file.exists():
            return

        try:
            data = yaml.safe_load(self.sources_file.read_text()) or {}
            for source_data in data.get("sources", []):
                self._user_sources.append(
                    Source(
                        type=source_data.get("type", "unknown"),
                        url=source_data.get("url"),
                        org=source_data.get("org"),
                        tag=source_data.get("tag", "palace-tasklist"),
                        official=source_data.get("official", False),
                        extra=source_data.get("extra", {}),
                    )
                )
        except (yaml.YAMLError, AttributeError):
            # Corrupted file, ignore
            pass

    def _save_user_sources(self) -> None:
        """Save user-configured sources to YAML file."""
        self.sources_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sources": [
                {
                    "type": s.type,
                    "url": s.url,
                    "org": s.org,
                    "tag": s.tag,
                    "official": s.official,
                    "extra": s.extra,
                }
                for s in self._user_sources
            ]
        }
        self.sources_file.write_text(yaml.dump(data, default_flow_style=False))

    def get_default_sources(self) -> list[Source]:
        """Get the default sources (always searched).

        Returns:
            List of default sources including official org and tag search.
        """
        return [
            # Official palace-ai org on HuggingFace
            Source(type="huggingface", org=OFFICIAL_ORG, official=True),
            # All HuggingFace datasets with palace-tasklist tag
            Source(type="huggingface", tag="palace-tasklist"),
            # All GitHub repos with palace-tasklist topic
            Source(type="github", tag="palace-tasklist"),
        ]

    def get_all_sources(self) -> list[Source]:
        """Get all sources (defaults + user-configured).

        Returns:
            Combined list of default and user sources.
        """
        return self.get_default_sources() + self._user_sources

    def get_user_sources(self) -> list[Source]:
        """Get user-configured sources only.

        Returns:
            List of user-configured sources.
        """
        return self._user_sources.copy()

    def add_source(self, url: str) -> Source:
        """Add a user source, auto-detecting type.

        Args:
            url: URL or path to add.

        Returns:
            The created Source object.
        """
        adapter_type, org, extra = detect_adapter(url)
        
        # Resolve collection_title to collection_slug if needed
        collection_title = extra.get("collection_title")
        collection_slug = extra.get("collection_slug")
        
        if collection_title and not collection_slug and org:
            # Need to look up the collection slug from the title
            resolved_slug = self._resolve_collection_slug(org, collection_title)
            if resolved_slug:
                collection_slug = resolved_slug
            else:
                raise ValueError(
                    f"Collection '{collection_title}' not found for user '{org}'. "
                    f"Check the collection URL or use the full collection page URL."
                )
        
        # Build extra dict - keep both slug (for API) and title (for display)
        source_extra = {}
        if collection_slug:
            source_extra["collection_slug"] = collection_slug
            # Store display name: use title if available, otherwise extract from slug
            if collection_title:
                source_extra["collection_name"] = f"{org}/{collection_title}"
            else:
                # Extract name from slug (remove the unique ID suffix)
                source_extra["collection_name"] = collection_slug
        
        source = Source(
            type=adapter_type,
            url=url,
            org=org,
            extra=source_extra,
        )
        self._user_sources.append(source)
        self._save_user_sources()
        return source

    def remove_source(self, url: str) -> bool:
        """Remove a user source.

        Args:
            url: URL or path to remove.

        Returns:
            True if source was found and removed.
        """
        original_count = len(self._user_sources)
        self._user_sources = [s for s in self._user_sources if s.url != url]

        if len(self._user_sources) < original_count:
            self._save_user_sources()
            return True
        return False

    def _resolve_collection_slug(self, org: str, title: str) -> str | None:
        """Resolve a collection title to its full slug.

        Args:
            org: Organization/user name.
            title: Collection title (from URL path).

        Returns:
            Full collection slug if found, None otherwise.
        """
        try:
            from huggingface_hub import list_collections
        except ImportError:
            return None

        title_lower = title.lower().replace("-", " ").replace("_", " ")

        try:
            for collection in list_collections(owner=org):
                # The slug format is: org/title-uniqueid
                # Extract the title part for comparison
                slug_parts = collection.slug.split("/")
                if len(slug_parts) < 2:
                    continue
                
                # Remove the unique ID suffix to get the title
                slug_title = slug_parts[1]
                # The title in slug has the unique ID at the end after a dash
                # e.g., "palace-698071045baae6945f7757e2" -> compare "palace"
                
                # Also check the actual collection title
                if collection.title and collection.title.lower() == title_lower:
                    return collection.slug
                
                # Check if the URL title matches the beginning of the slug
                if slug_title.lower().startswith(title_lower.replace(" ", "-")):
                    return collection.slug
                    
        except Exception:
            pass

        return None

    def discover_all(
        self,
        refresh: bool = False,
        on_error: Callable[[Any, Exception], None] | None = None,
    ) -> list[TasklistInfo]:
        """Discover tasklists from all sources.

        Args:
            refresh: Force refresh, ignoring cache.
            on_error: Callback for errors (receives source, exception).

        Returns:
            Aggregated list of discovered tasklists.
        """
        all_tasklists: list[TasklistInfo] = []
        seen_ids: set[str] = set()

        for source in self.get_all_sources():
            try:
                tasklists = self._discover_from_source(source, refresh=refresh)
                for tl in tasklists:
                    # Mark official if from palace-ai org
                    if source.official or (tl.id.startswith(f"{OFFICIAL_ORG}/")):
                        tl.official = True

                    # Deduplicate by ID
                    if tl.id not in seen_ids:
                        seen_ids.add(tl.id)
                        all_tasklists.append(tl)
            except RateLimitError:
                raise  # Re-raise rate limit errors
            except Exception as e:
                if on_error:
                    on_error(source, e)
                # Continue with other sources

        return all_tasklists

    def _discover_from_source(
        self,
        source: Source,
        refresh: bool = False,
    ) -> list[TasklistInfo]:
        """Discover tasklists from a single source.

        Args:
            source: Source to search.
            refresh: Force refresh, ignoring cache.

        Returns:
            List of discovered tasklists.
        """
        cache_key = source.key()

        # Check cache
        if not refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return [TasklistInfo(**tl) for tl in cached]

        # Handle HuggingFace collections specially
        collection_slug = source.extra.get("collection_slug") if source.extra else None
        if collection_slug and source.type == "huggingface":
            tasklists = self._discover_from_collection(collection_slug)
        else:
            # Fetch from adapter
            adapter = get_adapter(source.type)

            if source.org:
                tasklists = adapter.list_org(source.org, tag=source.tag)
            else:
                tasklists = adapter.list_by_tag(tag=source.tag)

        # Cache results
        self.cache.set(cache_key, [tl.__dict__ for tl in tasklists])

        return tasklists

    def _discover_from_collection(self, collection_slug: str) -> list[TasklistInfo]:
        """Discover tasklists from a HuggingFace collection.

        Args:
            collection_slug: The collection slug (e.g., "jrc-ai/palace-abc123").

        Returns:
            List of tasklists from datasets in the collection.
        """
        try:
            from huggingface_hub import get_collection
        except ImportError:
            return []

        tasklists: list[TasklistInfo] = []

        try:
            collection = get_collection(collection_slug)
        except Exception:
            # Collection not found or not accessible
            return []

        # Filter for datasets only
        for item in collection.items:
            if item.item_type != "dataset":
                continue

            # item.item_id is the dataset ID like "jrc-ai/my-dataset"
            dataset_id = item.item_id

            # Try to get info.json to check if it's a palace tasklist
            try:
                from huggingface_hub import hf_hub_download
                import json

                info_path = hf_hub_download(
                    repo_id=dataset_id,
                    filename="info.json",
                    repo_type="dataset",
                )
                with open(info_path) as f:
                    info = json.load(f)

                # It's a palace tasklist
                name = info.get("name", dataset_id.split("/")[-1])
                tasklists.append(
                    TasklistInfo(
                        name=name,
                        source="huggingface",
                        id=dataset_id,
                        description=info.get("description"),
                        category=info.get("category"),
                        task_type=info.get("task_type"),
                        url=f"https://huggingface.co/datasets/{dataset_id}",
                    )
                )
            except Exception:
                # Not a palace tasklist or can't access - skip
                continue

        return tasklists
