"""
Data Transfer Objects and domain models for the Essay Archive System.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class SourceFile:
    id: str
    content_sha256: str
    original_name: str
    media_type: str
    storage_key: str
    byte_size: int
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Page:
    id: str
    source_file_id: str
    physical_page: int
    orientation: int = 0
    preprocessing_version: int = 1
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentPage:
    document_id: str
    page_id: str
    order_index: int
    page_kind: str = "answer"  # cover, answer, other

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Document:
    id: str
    title: str
    company: str
    division: str
    role: str
    collection: str = "reference"  # own_draft, own_experience, reference, recruitment_notice
    author: Optional[str] = None
    recruitment_year: Optional[int] = None
    outcome: str = "unknown"  # pass, fail, unknown
    grouping_status: str = "provisional"  # provisional, confirmed
    completeness: str = "unknown"  # complete, partial, unknown
    notes: Optional[str] = None
    deleted_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Answer:
    id: str
    document_id: str
    question_number: int
    current_revision_id: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnswerRevision:
    id: str
    answer_id: str
    parent_revision_id: Optional[str]
    question_text: str
    body_text: str
    text_sha256: str
    origin: str = "manual"  # manual, ocr, rewrite
    review_status: str = "needs_user_review"  # needs_user_review, approved, rejected
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceSpan:
    id: str
    revision_id: str
    start_char: int
    end_char: int
    page_id: Optional[str] = None
    source_id: Optional[str] = None  # external or friendly source id
    bbox: Optional[List[float]] = None  # [ymin, xmin, ymax, xmax] 0~1 normalized
    uncertain: bool = False
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Tag:
    canonical_id: str
    facet: str  # company, division, role, question_type, competency, tech_tool, experience_type, industry, outcome_type, data_category
    label: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TagAlias:
    alias: str
    canonical_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TagAssignment:
    id: str
    target_id: str  # document_id or revision_id
    target_type: str  # document or revision
    tag_id: str
    origin: str = "manual"  # manual, suggested
    status: str = "suggested"  # suggested, accepted, rejected
    evidence_quote: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    id: str
    revision_id: str
    answer_id: str
    document_id: str
    start_char: int
    end_char: int
    kind: str  # answer, experience
    text: str
    index_generation: str
    content_hash: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Embedding:
    chunk_id: str
    provider: str
    model_id: str
    dimension: int
    task_config_hash: str
    vector: bytes  # float32 numpy array serialized as bytes
    index_generation: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Job:
    id: str
    kind: str  # ingest, ocr, embedding, tagging, rewrite
    target_id: str
    input_hash: str
    config_hash: str
    status: str = "queued"  # queued, running, succeeded, failed, review_required, cancelled
    attempt: int = 0
    lease_until: Optional[str] = None
    progress: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    result_json: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StyleProfile:
    id: str
    name: str
    features_json: str  # JSON formatted profile
    reference_revision_ids: List[str]
    extractor_version: int = 1
    accepted_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RewriteProposal:
    id: str
    input_revision_id: str
    output_text: str
    profile_id: Optional[str]
    facts_json: str
    diff_json: str
    validation_json: str
    model_config: str
    status: str = "suggested"  # suggested, accepted, rejected
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndexGeneration:
    id: str
    config_hash: str
    status: str = "building"  # building, active, retired
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
