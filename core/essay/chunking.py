"""
Text chunking engine with precise character offsets and answer/experience boundaries.
"""

from __future__ import annotations
import hashlib
import re
from typing import List
from core.essay.models import Chunk, new_uuid, utc_now_iso

MAX_CHUNK_CHARS = 800
MIN_CHUNK_CHARS = 100


class EssayChunker:
    @staticmethod
    def chunk_revision(
        revision_id: str,
        answer_id: str,
        document_id: str,
        body_text: str,
        index_generation: str = "gen_v1"
    ) -> List[Chunk]:
        """
        Splits an answer revision into chunks with exact character offsets.
        If body_text <= MAX_CHUNK_CHARS, returns a single 'answer' chunk.
        Otherwise, splits by double newline (paragraphs) or sub-headings into 'experience' chunks.
        """
        text = body_text.strip()
        if not text:
            return []

        chunks: List[Chunk] = []

        if len(text) <= MAX_CHUNK_CHARS:
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(Chunk(
                id=new_uuid(),
                revision_id=revision_id,
                answer_id=answer_id,
                document_id=document_id,
                start_char=0,
                end_char=len(text),
                kind="answer",
                text=text,
                index_generation=index_generation,
                content_hash=content_hash,
                created_at=utc_now_iso()
            ))
            return chunks

        # Split on paragraph boundaries (two or more newlines)
        pattern = re.compile(r"\n\s*\n")
        matches = list(pattern.finditer(body_text))

        if not matches:
            # Fallback: single chunk if no paragraph boundaries
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            chunks.append(Chunk(
                id=new_uuid(),
                revision_id=revision_id,
                answer_id=answer_id,
                document_id=document_id,
                start_char=0,
                end_char=len(text),
                kind="answer",
                text=text,
                index_generation=index_generation,
                content_hash=content_hash,
                created_at=utc_now_iso()
            ))
            return chunks

        cur_start = 0
        for m in matches:
            seg_text = body_text[cur_start:m.start()].strip()
            if len(seg_text) >= MIN_CHUNK_CHARS:
                content_hash = hashlib.sha256(seg_text.encode("utf-8")).hexdigest()
                chunks.append(Chunk(
                    id=new_uuid(),
                    revision_id=revision_id,
                    answer_id=answer_id,
                    document_id=document_id,
                    start_char=cur_start,
                    end_char=m.start(),
                    kind="experience",
                    text=seg_text,
                    index_generation=index_generation,
                    content_hash=content_hash,
                    created_at=utc_now_iso()
                ))
                cur_start = m.end()

        # Last segment
        remaining = body_text[cur_start:].strip()
        if remaining:
            content_hash = hashlib.sha256(remaining.encode("utf-8")).hexdigest()
            chunks.append(Chunk(
                id=new_uuid(),
                revision_id=revision_id,
                answer_id=answer_id,
                document_id=document_id,
                start_char=cur_start,
                end_char=len(body_text),
                kind="experience",
                text=remaining,
                index_generation=index_generation,
                content_hash=content_hash,
                created_at=utc_now_iso()
            ))

        return chunks
