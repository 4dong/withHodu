"""
Tag dictionary, alias management, and evidence-backed tag suggestions for Essay Archive.
"""

from __future__ import annotations
import re
from typing import List, Tuple, Optional
from core.essay.models import Tag, TagAssignment
from core.essay.repository import EssayRepository

STANDARD_FACETS = [
    "company", "division", "role", "question_type", "competency",
    "tech_tool", "experience_type", "industry", "outcome_type", "data_category"
]

# Standard technical terms and aliases
BUILTIN_ALIASES = {
    "파이토치": "tech_tool:PyTorch",
    "pytorch": "tech_tool:PyTorch",
    "PyTorch": "tech_tool:PyTorch",
    "1D-CNN": "tech_tool:1D-CNN",
    "1d-cnn": "tech_tool:1D-CNN",
    "CANalyzer": "tech_tool:CANalyzer",
    "canalyzer": "tech_tool:CANalyzer",
    "FRAM": "tech_tool:FRAM",
    "fram": "tech_tool:FRAM",
    "소프트웨어 품질": "role:SW 품질",
    "sw 품질": "role:SW 품질",
    "SW품질": "role:SW 품질",
    "품질보증": "role:품질보증",
    "품질 본부": "division:품질본부",
    "전동화": "industry:전동화/EV",
    "EV": "industry:전동화/EV",
    "SDV": "industry:SDV",
    "CAD": "tech_tool:CAD",
}

# Regex for exact technical term extraction (uses alphanumeric lookarounds to handle attached Korean particles like ~와, ~를, ~로)
KNOWN_TECH_PATTERNS = [
    (r"(?<![A-Za-z0-9])PyTorch(?![A-Za-z0-9])", "tech_tool", "PyTorch"),
    (r"(?<![A-Za-z0-9])1D-CNN(?![A-Za-z0-9])", "tech_tool", "1D-CNN"),
    (r"(?<![A-Za-z0-9])CANalyzer(?![A-Za-z0-9])", "tech_tool", "CANalyzer"),
    (r"(?<![A-Za-z0-9])FRAM(?![A-Za-z0-9])", "tech_tool", "FRAM"),
    (r"(?<![A-Za-z0-9])EV(?![A-Za-z0-9])", "industry", "EV"),
    (r"(?<![A-Za-z0-9])SW(?![A-Za-z0-9])", "industry", "SW"),
    (r"(?<![A-Za-z0-9])SDV(?![A-Za-z0-9])", "industry", "SDV"),
    (r"(?<![A-Za-z0-9])PV5(?![A-Za-z0-9])", "tech_tool", "PV5"),
    (r"(?<![A-Za-z0-9])CAD(?![A-Za-z0-9])", "tech_tool", "CAD"),
]


class TagService:
    def __init__(self, repository: EssayRepository):
        self.repo = repository
        self._init_builtin_tags()

    def _init_builtin_tags(self):
        with self.repo.get_connection() as conn:
            for alias, canonical_id in BUILTIN_ALIASES.items():
                facet, label = canonical_id.split(":", 1)
                conn.execute(
                    "INSERT OR IGNORE INTO tags (canonical_id, facet, label) VALUES (?, ?, ?)",
                    (canonical_id, facet, label)
                )
                conn.execute(
                    "INSERT OR IGNORE INTO tag_aliases (alias, canonical_id) VALUES (?, ?)",
                    (alias, canonical_id)
                )
            conn.commit()

    def resolve_tag(self, term: str) -> Optional[Tag]:
        """Resolves term or alias to canonical Tag."""
        with self.repo.get_connection() as conn:
            cur = conn.execute("SELECT canonical_id FROM tag_aliases WHERE alias = ?", (term.strip(),))
            row = cur.fetchone()
            if row:
                canon_id = row["canonical_id"]
                facet, label = canon_id.split(":", 1)
                return Tag(canonical_id=canon_id, facet=facet, label=label)

            # Check direct match
            cur = conn.execute("SELECT canonical_id, facet, label FROM tags WHERE label = ? OR canonical_id = ?", (term.strip(), term.strip()))
            row = cur.fetchone()
            if row:
                return Tag(canonical_id=row["canonical_id"], facet=row["facet"], label=row["label"])
        return None

    def extract_deterministic_tags(self, text: str) -> List[Tuple[Tag, str]]:
        """
        Extracts tags backed by exact substring evidence in the text.
        Returns list of (Tag, evidence_quote).
        """
        results = []
        for pattern, facet, label in KNOWN_TECH_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                tag = self.repo.ensure_tag(facet, label)
                evidence = match.group(0)
                results.append((tag, evidence))
        return results

    def suggest_and_assign_tags_for_revision(self, revision_id: str) -> List[TagAssignment]:
        """
        Generates evidence-backed tag suggestions for an answer revision without
        overwriting existing manual or accepted tags.
        """
        rev = self.repo.get_revision(revision_id)
        if not rev:
            return []

        existing_tags = self.repo.get_tags_for_target(revision_id)
        existing_canonical_ids = {t.canonical_id for t, _ in existing_tags}

        deterministic = self.extract_deterministic_tags(rev.body_text + " " + rev.question_text)
        new_assignments = []

        for tag, evidence in deterministic:
            if tag.canonical_id not in existing_canonical_ids:
                assignment = self.repo.assign_tag(
                    target_id=revision_id,
                    target_type="revision",
                    tag_id=tag.canonical_id,
                    origin="suggested",
                    status="suggested",
                    evidence_quote=evidence
                )
                new_assignments.append(assignment)

        return new_assignments

    def accept_tag(self, target_id: str, tag_id: str):
        self.repo.set_tag_status(target_id, tag_id, status="accepted")

    def reject_tag(self, target_id: str, tag_id: str):
        self.repo.set_tag_status(target_id, tag_id, status="rejected")
