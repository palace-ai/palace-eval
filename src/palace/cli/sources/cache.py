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

"""Cache management for source listings."""

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from palace.utils.paths import USER_DIR

# Cache TTL in seconds (1 hour)
CACHE_TTL = 3600

CACHE_FILE = USER_DIR / "sources_cache.json"


@dataclass
class CacheEntry:
    """A cached source listing."""

    source_key: str
    timestamp: float
    data: list[dict[str, Any]]


class SourceCache:
    """Manages caching of source listings with 1-hour TTL."""

    def __init__(self, cache_file: Path = CACHE_FILE):
        self.cache_file = cache_file
        self._cache: dict[str, CacheEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text())
                for key, entry in data.items():
                    self._cache[key] = CacheEntry(
                        source_key=entry["source_key"],
                        timestamp=entry["timestamp"],
                        data=entry["data"],
                    )
            except (json.JSONDecodeError, KeyError):
                # Corrupted cache, start fresh
                self._cache = {}

    def _save(self) -> None:
        """Save cache to disk."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = {key: asdict(entry) for key, entry in self._cache.items()}
        self.cache_file.write_text(json.dumps(data, indent=2))

    def get(self, source_key: str) -> list[dict[str, Any]] | None:
        """Get cached data if valid (not expired).

        Args:
            source_key: Unique key for the source.

        Returns:
            Cached data or None if not cached or expired.
        """
        entry = self._cache.get(source_key)
        if entry is None:
            return None

        if time.time() - entry.timestamp > CACHE_TTL:
            # Expired
            return None

        return entry.data

    def set(self, source_key: str, data: list[dict[str, Any]]) -> None:
        """Cache data for a source.

        Args:
            source_key: Unique key for the source.
            data: Data to cache.
        """
        self._cache[source_key] = CacheEntry(
            source_key=source_key,
            timestamp=time.time(),
            data=data,
        )
        self._save()

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with size, item_count, oldest_entry, etc.
        """
        if not self._cache:
            return {
                "item_count": 0,
                "size_bytes": 0,
                "oldest_timestamp": None,
                "newest_timestamp": None,
            }

        timestamps = [e.timestamp for e in self._cache.values()]
        size = self.cache_file.stat().st_size if self.cache_file.exists() else 0

        return {
            "item_count": len(self._cache),
            "size_bytes": size,
            "oldest_timestamp": min(timestamps),
            "newest_timestamp": max(timestamps),
        }
