"""
Per-paper reading record kept inside the paper folder, so it moves, renames and deletes with the paper.

    <paper_dir>/reading.json              last page read
    <paper_dir>/translations/page_N.json  best translation of page N so far

Translations have tiers by the model that actually produced them: Google 0 < Gemini 2.5 < 3.5 < 3.7.
A stored page is reused when its tier is at least the selected engine's, so a page read once with
Gemini 3.7 opens instantly and without an API call under any engine. A save never replaces a higher
tier; an equal tier may be replaced (retranslation, changed prompt).
"""

import hashlib
import json
import os
import re
import time
from typing import Any, Dict, Optional

# Bump when parsing, translation scope or reading order change: stored pages from older layouts are ignored.
LAYOUT_VERSION = "2026_08_25_v8_self_contained_hover_sync_guaranteed+scope-1+formula-1"

READING_FILE = "reading.json"
TRANSLATIONS_DIR = "translations"


def engine_tier(engine: str) -> float:
    """Tier the selected engine would produce: 'Gemini 3.7 Flash' -> 3.7, Google -> 0."""
    match = re.search(r"Gemini (\d+(?:\.\d+)?)", engine or "")
    return float(match.group(1)) if match else 0.0


def result_tier(result: Dict[str, Any]) -> float:
    """Tier a translation really has; a Gemini request that fell back to Google is Google quality."""
    if result.get("is_fallback"):
        return 0.0
    match = re.search(r"gemini-(\d+(?:\.\d+)?)", result.get("model_used") or "")
    return float(match.group(1)) if match else 0.0


def tier_label(tier: float) -> str:
    return f"Gemini {tier:g}" if tier else "Google 번역"


def prompt_key(custom_prompt: Optional[str]) -> str:
    return hashlib.sha1(custom_prompt.encode("utf-8")).hexdigest()[:12] if custom_prompt else ""


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


class ReadingStore:
    def __init__(self, paper_dir: str, layout_version: str = LAYOUT_VERSION):
        self.paper_dir = paper_dir
        # Pages saved under another parser/highlighter layout carry stale boxes and are ignored.
        self.layout_version = layout_version

    def _page_path(self, page: int) -> str:
        return os.path.join(self.paper_dir, TRANSLATIONS_DIR, f"page_{int(page)}.json")

    def _stored(self, page: int) -> Optional[Dict[str, Any]]:
        entry = _read_json(self._page_path(page))
        if not entry or entry.get("layout_version") != self.layout_version or "result" not in entry:
            return None
        return entry

    def load_page(self, page: int, engine: str, custom_prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Stored translation good enough for the selected engine, or None."""
        entry = self._stored(page)
        if not entry:
            return None
        wanted = engine_tier(engine)
        tier = float(entry.get("tier", 0))
        if tier > wanted or (tier == wanted and (tier == 0 or entry.get("prompt_key") == prompt_key(custom_prompt))):
            result = dict(entry["result"])
            result["from_store"] = True
            result["stored_tier"] = tier
            return result
        return None

    def save_page(self, page: int, result: Dict[str, Any], custom_prompt: Optional[str] = None) -> bool:
        """Keeps a fully translated page unless a higher tier is already stored."""
        if not isinstance(result, dict) or "pairs" not in result or result.get("failed_count"):
            return False
        tier = result_tier(result)
        existing = self._stored(page)
        if existing and float(existing.get("tier", 0)) > tier:
            return False
        clean = {k: v for k, v in result.items() if k not in ("from_store", "stored_tier")}
        _write_json(self._page_path(page), {
            "tier": tier,
            "prompt_key": prompt_key(custom_prompt) if tier else "",
            "layout_version": self.layout_version,
            "saved_at": time.time(),
            "result": clean,
        })
        return True

    def translated_pages(self) -> Dict[int, float]:
        """Page number -> stored tier."""
        folder = os.path.join(self.paper_dir, TRANSLATIONS_DIR)
        pages = {}
        try:
            names = os.listdir(folder)
        except OSError:
            return pages
        for name in names:
            match = re.fullmatch(r"page_(\d+)\.json", name)
            if match:
                entry = self._stored(int(match.group(1)))
                if entry:
                    pages[int(match.group(1))] = float(entry.get("tier", 0))
        return pages

    def progress(self) -> Dict[str, Any]:
        return _read_json(os.path.join(self.paper_dir, READING_FILE)) or {}

    def record_page(self, page: int, total_pages: int) -> None:
        """Remembers the page on screen; skips the write when nothing changed."""
        current = self.progress()
        if current.get("last_page") == page and current.get("total_pages") == total_pages:
            return
        _write_json(os.path.join(self.paper_dir, READING_FILE), {
            "last_page": int(page),
            "total_pages": int(total_pages),
            "updated_at": time.time(),
        })


def latest_read(archive_root: str) -> Optional[Dict[str, Any]]:
    """Most recently read paper in the archive: {"paper_dir", "last_page", "total_pages", "updated_at"}."""
    latest = None
    try:
        topics = os.listdir(archive_root)
    except OSError:
        return None
    for topic in topics:
        topic_dir = os.path.join(archive_root, topic)
        if topic.startswith((".", "_")) or not os.path.isdir(topic_dir):
            continue
        for name in os.listdir(topic_dir):
            paper_dir = os.path.join(topic_dir, name)
            progress = _read_json(os.path.join(paper_dir, READING_FILE))
            if progress and progress.get("last_page") and os.path.isfile(os.path.join(paper_dir, "metadata.json")):
                if not latest or progress.get("updated_at", 0) > latest.get("updated_at", 0):
                    latest = dict(progress, paper_dir=paper_dir)
    return latest
