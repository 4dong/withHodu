"""
Hybrid Search Engine combining FTS5 trigram/exact matching and exact cosine vector search with RRF.
"""

from __future__ import annotations
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from core.essay.models import utc_now_iso
from core.essay.repository import EssayRepository
from core.essay.chunking import EssayChunker
from core.essay.embedding import BaseEmbeddingProvider


@dataclass
class SearchResultItem:
    chunk_id: str
    revision_id: str
    answer_id: str
    document_id: str
    document_title: str
    company: str
    role: str
    collection: str
    question_number: int
    question_text: str
    text: str
    score: float
    match_origin: str  # hybrid, keyword, vector
    start_char: int
    end_char: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    hits: List[SearchResultItem]
    mode: str  # hybrid, keyword_only
    total_hits: int
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": [h.to_dict() for h in self.hits],
            "mode": self.mode,
            "total_hits": self.total_hits,
            "warning": self.warning
        }


class EssaySearchEngine:
    def __init__(self, repository: EssayRepository, embedding_provider: Optional[BaseEmbeddingProvider] = None):
        self.repo = repository
        self.embedding_provider = embedding_provider

    # -------------------------------------------------------------------------
    # Indexing
    # -------------------------------------------------------------------------
    def index_revision(self, revision_id: str, index_generation: str = "gen_v1"):
        """Indexes an answer revision into chunks, FTS5, and vector embeddings."""
        rev = self.repo.get_revision(revision_id)
        if not rev:
            return

        ans = self.repo.get_answer(rev.answer_id)
        if not ans:
            return

        doc = self.repo.get_document(ans.document_id)
        if not doc or doc.deleted_at:
            return

        chunks = EssayChunker.chunk_revision(
            revision_id=rev.id,
            answer_id=ans.id,
            document_id=doc.id,
            body_text=rev.body_text,
            index_generation=index_generation
        )

        with self.repo.get_connection() as conn:
            # 1. Remove outdated chunks and FTS entries for this answer
            cur = conn.execute("SELECT id FROM chunks WHERE answer_id = ?", (ans.id,))
            old_chunk_ids = [r["id"] for r in cur.fetchall()]
            for c_id in old_chunk_ids:
                conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (c_id,))
                conn.execute("DELETE FROM embeddings WHERE chunk_id = ?", (c_id,))
            conn.execute("DELETE FROM chunks WHERE answer_id = ?", (ans.id,))

            # 2. Insert new chunks and FTS
            for chunk in chunks:
                conn.execute(
                    """INSERT INTO chunks (id, revision_id, answer_id, document_id, start_char, end_char, kind, text, index_generation, content_hash, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (chunk.id, chunk.revision_id, chunk.answer_id, chunk.document_id,
                     chunk.start_char, chunk.end_char, chunk.kind, chunk.text,
                     chunk.index_generation, chunk.content_hash, chunk.created_at)
                )
                try:
                    conn.execute(
                        """INSERT INTO chunks_fts (chunk_id, document_id, answer_id, revision_id, text)
                           VALUES (?, ?, ?, ?, ?)""",
                        (chunk.id, chunk.document_id, chunk.answer_id, chunk.revision_id, chunk.text)
                    )
                except Exception:
                    pass

            conn.commit()

        # 3. Vector embeddings if provider available
        if self.embedding_provider and chunks:
            texts = [f"{doc.company} {doc.role} {rev.question_text}\n{c.text}" for c in chunks]
            try:
                vectors = self.embedding_provider.embed_documents(texts)
                now = utc_now_iso()
                with self.repo.get_connection() as conn:
                    for chunk, vec in zip(chunks, vectors):
                        vec_bytes = vec.astype(np.float32).tobytes()
                        conn.execute(
                            """INSERT OR REPLACE INTO embeddings (chunk_id, provider, model_id, dimension, task_config_hash, vector, index_generation, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (chunk.id, "gemini", self.embedding_provider.model_id,
                             self.embedding_provider.dimension, "config_v1", vec_bytes, index_generation, now)
                        )
                    conn.commit()
            except Exception as e:
                # Log or tolerate embedding failure; keyword index remains valid
                pass

    def index_all_approved(self, index_generation: str = "gen_v1", allow_unreviewed: bool = False):
        """Builds index for all active documents and current revisions."""
        docs = self.repo.list_documents(include_deleted=False)
        for doc in docs:
            answers = self.repo.get_answers_for_document(doc.id)
            for ans, rev in answers:
                if rev:
                    if allow_unreviewed or rev.review_status == "approved":
                        self.index_revision(rev.id, index_generation=index_generation)

    # -------------------------------------------------------------------------
    # Search Operations
    # -------------------------------------------------------------------------
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        index_generation: str = "gen_v1"
    ) -> SearchResponse:
        """
        Executes hybrid search (FTS5 + Cosine) or falls back to Keyword Search.
        """
        filters = filters or {}
        cleaned_query = query.strip()
        if not cleaned_query:
            return SearchResponse(hits=[], mode="empty", total_hits=0)

        # 1. Keyword search (FTS + exact matching)
        keyword_hits = self._search_keyword(cleaned_query, filters, limit=30)

        # 2. Vector search (if embedding provider available)
        vector_hits = []
        vector_failed = False
        if self.embedding_provider:
            try:
                vector_hits = self._search_vector(cleaned_query, filters, limit=30, index_generation=index_generation)
            except Exception:
                vector_failed = True

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF formula: sum(1.0 / (60.0 + rank))
        rrf_scores: Dict[str, float] = {}
        items_map: Dict[str, Tuple[Dict[str, Any], str]] = {}

        for rank, item in enumerate(keyword_hits):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            items_map[cid] = (item, "keyword")

        for rank, item in enumerate(vector_hits):
            cid = item["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            origin = "hybrid" if cid in items_map else "vector"
            items_map[cid] = (item, origin)

        # Sort combined hits
        sorted_cids = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)[:limit]

        final_hits: List[SearchResultItem] = []
        for cid in sorted_cids:
            raw_item, origin = items_map[cid]
            final_hits.append(SearchResultItem(
                chunk_id=raw_item["chunk_id"],
                revision_id=raw_item["revision_id"],
                answer_id=raw_item["answer_id"],
                document_id=raw_item["document_id"],
                document_title=raw_item["document_title"],
                company=raw_item["company"],
                role=raw_item["role"],
                collection=raw_item["collection"],
                question_number=raw_item["question_number"],
                question_text=raw_item["question_text"],
                text=raw_item["text"],
                score=rrf_scores[cid],
                match_origin=origin,
                start_char=raw_item["start_char"],
                end_char=raw_item["end_char"]
            ))

        mode = "keyword_only" if (not self.embedding_provider or vector_failed) else "hybrid"
        warning = "벡터 검색 공급자 오류로 키워드 검색 모드로 동작했습니다." if vector_failed else None

        return SearchResponse(
            hits=final_hits,
            mode=mode,
            total_hits=len(final_hits),
            warning=warning
        )

    def _build_filter_sql(self, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
        clauses = ["d.deleted_at IS NULL"]
        params: List[Any] = []

        # A05: Default search must exclude unreviewed revisions
        include_unreviewed = filters.get("include_unreviewed", False)
        if not include_unreviewed:
            clauses.append("r.review_status = 'approved'")

        if "document_id" in filters and filters["document_id"]:
            clauses.append("d.id = ?")
            params.append(filters["document_id"])
        if "company" in filters and filters["company"]:
            clauses.append("d.company = ?")
            params.append(filters["company"])
        if "role" in filters and filters["role"]:
            clauses.append("d.role = ?")
            params.append(filters["role"])
        if "collection" in filters and filters["collection"]:
            clauses.append("d.collection = ?")
            params.append(filters["collection"])

        return (" AND " + " AND ".join(clauses)) if clauses else "", params

    def _search_keyword(self, query: str, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        filter_sql, params = self._build_filter_sql(filters)

        # Tokenize query tokens safely
        raw_tokens = re.findall(r"[A-Za-z0-9가-힣]+", query)
        short_tokens = [t for t in raw_tokens if len(t) < 3]
        long_tokens = [t for t in raw_tokens if len(t) >= 3]

        with self.repo.get_connection() as conn:
            # First try FTS5 if tokens >= 3
            fts_chunk_ids = []
            if long_tokens:
                fts_query_str = " OR ".join(f'"{t}"' for t in long_tokens)
                try:
                    cur = conn.execute(
                        "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 50",
                        (fts_query_str,)
                    )
                    fts_chunk_ids = [r["chunk_id"] for r in cur.fetchall()]
                except Exception:
                    pass

            # Construct SQL for candidate chunks
            query_parts = []
            query_params: List[Any] = []

            if fts_chunk_ids:
                placeholders = ",".join("?" for _ in fts_chunk_ids)
                query_parts.append(f"c.id IN ({placeholders})")
                query_params.extend(fts_chunk_ids)

            # Exact substring matching for all tokens (especially short tokens like EV, SW)
            for token in raw_tokens:
                query_parts.append("(c.text LIKE ? OR r.question_text LIKE ?)")
                query_params.extend([f"%{token}%", f"%{token}%"])

            match_clause = ("(" + " OR ".join(query_parts) + ")") if query_parts else "1=1"

            # Calculate match score based on number of matched tokens
            score_exprs = []
            score_params = []
            for token in raw_tokens:
                score_exprs.append("(CASE WHEN c.text LIKE ? OR r.question_text LIKE ? THEN 1 ELSE 0 END)")
                score_params.extend([f"%{token}%", f"%{token}%"])

            score_sql = " + ".join(score_exprs) if score_exprs else "0"

            sql = f"""
                SELECT c.id as chunk_id, c.revision_id, c.answer_id, c.document_id,
                       c.start_char, c.end_char, c.text,
                       d.title as document_title, d.company, d.role, d.collection,
                       a.question_number, r.question_text,
                       ({score_sql}) as keyword_match_score
                FROM chunks c
                JOIN answers a ON c.answer_id = a.id
                JOIN answer_revisions r ON c.revision_id = r.id
                JOIN documents d ON c.document_id = d.id
                WHERE a.current_revision_id = c.revision_id
                  AND {match_clause}
                  {filter_sql}
                ORDER BY keyword_match_score DESC
                LIMIT ?
            """
            final_params = score_params + query_params + params + [limit]
            cur = conn.execute(sql, final_params)
            rows = [dict(r) for r in cur.fetchall()]
            return rows

    def _search_vector(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int,
        index_generation: str
    ) -> List[Dict[str, Any]]:
        if not self.embedding_provider:
            return []

        q_vec = self.embedding_provider.embed_query(query)
        filter_sql, params = self._build_filter_sql(filters)

        with self.repo.get_connection() as conn:
            sql = f"""
                SELECT c.id as chunk_id, c.revision_id, c.answer_id, c.document_id,
                       c.start_char, c.end_char, c.text,
                       d.title as document_title, d.company, d.role, d.collection,
                       a.question_number, r.question_text,
                       e.vector
                FROM chunks c
                JOIN answers a ON c.answer_id = a.id
                JOIN answer_revisions r ON c.revision_id = r.id
                JOIN documents d ON c.document_id = d.id
                JOIN embeddings e ON c.id = e.chunk_id
                WHERE a.current_revision_id = c.revision_id
                  AND e.index_generation = ?
                  AND e.model_id = ?
                  {filter_sql}
            """
            cur = conn.execute(sql, [index_generation, self.embedding_provider.model_id] + params)
            rows = cur.fetchall()
            if not rows:
                return []

            candidate_items = []
            vectors = []
            for r in rows:
                item = dict(r)
                vec_blob = item.pop("vector")
                vec = np.frombuffer(vec_blob, dtype=np.float32)
                vectors.append(vec)
                candidate_items.append(item)

            matrix = np.vstack(vectors)  # shape (N, D)
            sims = np.dot(matrix, q_vec)  # cosine similarity

            top_indices = np.argsort(sims)[::-1][:limit]
            results = []
            for idx in top_indices:
                it = candidate_items[idx]
                it["cosine_similarity"] = float(sims[idx])
                results.append(it)

            return results
