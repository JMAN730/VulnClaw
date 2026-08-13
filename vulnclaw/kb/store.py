"""VulnClaw Knowledge Store — manage and persist security knowledge base."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from vulnclaw.config.settings import KB_DIR

_TITLE_MAX = 80


class KnowledgeStore:
    """Manages the security knowledge base.

    Knowledge entries are stored as JSON files in the KB directory,
    organized by category (cve, techniques, protocols, tools, payloads,
    experience).
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self.store_dir = Path(store_dir) if store_dir else KB_DIR
        self._index: dict[str, list[dict[str, Any]]] = {}
        self._ensure_dirs()
        self._load_index()

    def _ensure_dirs(self) -> None:
        """Create KB directory structure."""
        for category in ["cve", "techniques", "protocols", "tools", "payloads", "experience"]:
            (self.store_dir / category).mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> None:
        """Load or build the KB index."""
        index_file = self.store_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._index = raw if isinstance(raw, dict) else {}
            except (json.JSONDecodeError, IOError):
                self._index = {}
        else:
            self._index = {}
            self._build_index()
            self._save_index()

    def _build_index(self) -> None:
        """Scan KB directory and build index."""
        self._index = {}
        if not self.store_dir.exists():
            return
        for category_dir in self.store_dir.iterdir():
            if not category_dir.is_dir() or category_dir.name == "memory":
                continue
            category = category_dir.name
            self._index[category] = []
            for entry_file in category_dir.glob("*.json"):
                try:
                    with open(entry_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        continue
                    self._index[category].append(
                        self.index_meta_for(data, entry_file)
                    )
                except (json.JSONDecodeError, IOError, TypeError, ValueError):
                    continue

    def _save_index(self) -> None:
        """Persist the index to disk."""
        index_file = self.store_dir / "index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)

    @staticmethod
    def normalize_tags(data: dict[str, Any]) -> list[str]:
        """Flatten entry tags into a list of searchable strings.

        Accepts both free-form KB ``tags: list[str]`` and experience
        ``tags: {tech[], vuln_type, waf, service}`` shapes, and always
        appends a ``status:`` token when ``status`` is present on the entry.
        """
        tags = data.get("tags", [])
        out: list[str] = []
        if isinstance(tags, list):
            out.extend(str(t).strip() for t in tags if str(t).strip())
        elif isinstance(tags, dict):
            for tech in tags.get("tech") or []:
                value = str(tech).strip()
                if value:
                    out.append(value)
            for key in ("vuln_type", "waf", "service"):
                value = str(tags.get(key) or "").strip()
                if value:
                    out.append(value)
        status = data.get("status")
        if status:
            token = f"status:{status}"
            if token not in out:
                out.append(token)
        # Preserve order, drop empties/duplicates.
        return list(dict.fromkeys(t for t in out if t))

    @classmethod
    def entry_title(cls, data: dict[str, Any], entry_id: str) -> str:
        """Best human-readable title for index/search consumers."""
        for key in ("title", "lesson", "context"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                return text if len(text) <= _TITLE_MAX else text[:_TITLE_MAX]
        return entry_id

    @staticmethod
    def entry_search_text(data: dict[str, Any], entry_id: str) -> str:
        """Untruncated text used for index-backed searches."""
        for key in ("title", "lesson", "context"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return entry_id

    @classmethod
    def index_meta_for(cls, data: dict[str, Any], filepath: Path | str) -> dict[str, Any]:
        """Build one index row from on-disk entry data."""
        path = Path(filepath)
        entry_id = str(data.get("id") or path.stem)
        meta: dict[str, Any] = {
            "id": entry_id,
            "title": cls.entry_title(data, entry_id),
            "search_text": cls.entry_search_text(data, entry_id),
            "tags": cls.normalize_tags(data),
            "file": str(path),
        }
        status = data.get("status")
        if status is not None and status != "":
            meta["status"] = status
        return meta

    def upsert_index_entry(
        self,
        category: str,
        entry_id: str,
        filepath: Path | str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Replace-or-append a single index row and persist.

        Calling this repeatedly for the same ``entry_id`` never creates
        duplicate rows — updates overwrite the previous meta.
        """
        payload = dict(data)
        payload["id"] = entry_id
        meta = self.index_meta_for(payload, filepath)
        metas = self._index.setdefault(category, [])
        metas[:] = [row for row in metas if row.get("id") != entry_id]
        metas.append(meta)
        self._save_index()
        return meta

    def remove_index_entry(self, category: str, entry_id: str) -> bool:
        """Drop an entry from the in-memory + on-disk index. True if removed."""
        metas = self._index.get(category)
        if not metas:
            return False
        before = len(metas)
        metas[:] = [row for row in metas if row.get("id") != entry_id]
        if len(metas) == before:
            return False
        self._save_index()
        return True

    def rebuild_index(self) -> dict[str, int]:
        """Rescan category directories and rewrite ``index.json`` from disk.

        Safe migration path for experience (or other) files written without
        an index update. Returns category counts after rebuild.
        """
        self._build_index()
        self._save_index()
        return self.get_stats()

    def add_entry(self, category: str, entry_id: str, data: dict[str, Any]) -> Path:
        """Add or replace a knowledge entry.

        Args:
            category: Category (cve, techniques, protocols, tools, payloads, experience).
            entry_id: Unique entry identifier.
            data: Entry data dict.

        Returns:
            Path to the saved file.

        Index rows are upserted by id so re-adding the same entry never
        leaves duplicate rows in ``index.json``.
        """
        category_dir = self.store_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)

        data["id"] = entry_id
        filepath = category_dir / f"{entry_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.upsert_index_entry(category, entry_id, filepath, data)
        return filepath

    def delete_entry(self, category: str, entry_id: str) -> bool:
        """Delete an entry file and its index row. True when a file was removed."""
        filepath = self.store_dir / category / f"{entry_id}.json"
        removed_file = False
        if filepath.exists():
            filepath.unlink()
            removed_file = True
        removed_index = self.remove_index_entry(category, entry_id)
        return removed_file or removed_index

    def get_entry(self, category: str, entry_id: str) -> Optional[dict[str, Any]]:
        """Get a knowledge entry by category and ID."""
        filepath = self.store_dir / category / f"{entry_id}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Search the knowledge base.

        Args:
            query: Search query string.
            category: Limit to a specific category.
            tags: Filter by tags.

        Returns:
            List of matching entries.
        """
        results = []
        query_lower = query.lower()

        categories = [category] if category else list(self._index.keys())

        for cat in categories:
            for entry_meta in self._index.get(cat, []):
                # Check tags
                if tags and not any(t in entry_meta.get("tags", []) for t in tags):
                    continue

                # Check query
                entry_id = entry_meta.get("id", "").lower()
                entry_title = entry_meta.get("title", "").lower()
                entry_search_text = entry_meta.get("search_text", entry_title).lower()
                entry_tags = " ".join(str(t) for t in entry_meta.get("tags", [])).lower()
                entry_status = str(entry_meta.get("status", "")).lower()

                if (
                    query_lower in entry_id
                    or query_lower in entry_title
                    or query_lower in entry_search_text
                    or query_lower in entry_tags
                    or (entry_status and query_lower in entry_status)
                ):
                    # Load full entry
                    filepath = entry_meta.get("file")
                    if filepath and Path(filepath).exists():
                        with open(filepath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        data["_category"] = cat
                        results.append(data)

        return results

    def iter_all_entries(self) -> list[dict[str, Any]]:
        """Load and return every knowledge entry across all categories.

        Each returned dict is the full entry data with an extra `_category`
        field. Entries that fail to load are skipped. Used by keyword-based
        retrieval which needs the full corpus in memory.
        """
        entries: list[dict[str, Any]] = []
        for cat, metas in self._index.items():
            for entry_meta in metas:
                filepath = entry_meta.get("file")
                if not filepath or not Path(filepath).exists():
                    continue
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    continue
                data["_category"] = cat
                entries.append(data)
        return entries

    def list_categories(self) -> list[str]:
        """List all knowledge categories."""
        return list(self._index.keys())

    def list_entries(self, category: str) -> list[dict[str, Any]]:
        """List all entries in a category."""
        return self._index.get(category, [])

    def get_stats(self) -> dict[str, int]:
        """Get knowledge base statistics."""
        return {cat: len(entries) for cat, entries in self._index.items()}
