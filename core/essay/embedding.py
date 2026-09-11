"""
Embedding Providers and Vector Validation for Essay Chunk Retrieval.
"""

from __future__ import annotations
import abc
import hashlib
import json
import urllib.request
import urllib.error
import numpy as np
from typing import List, Optional

from core.key_manager import KeyManager


class BaseEmbeddingProvider(abc.ABC):
    @property
    @abc.abstractmethod
    def model_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        pass

    @abc.abstractmethod
    def embed_documents(self, texts: List[str]) -> List[np.ndarray]:
        pass

    @abc.abstractmethod
    def embed_query(self, query: str) -> np.ndarray:
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock embedding provider for tests and offline operation.
    Generates unit-normalized vectors using character n-gram hashing invariant to PYTHONHASHSEED.
    """

    def __init__(self, dimension: int = 128, model_id: str = "mock-embedding-v1"):
        self._dim = dimension
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dim

    def _embed_single(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        if not text:
            vec[0] = 1.0
            return vec

        # Use character 2-grams and 3-grams to create deterministic pseudo-dense vector invariant to PYTHONHASHSEED (A19)
        for i in range(len(text) - 1):
            gram = text[i:i + 2]
            h = int(hashlib.md5(gram.encode('utf-8')).hexdigest(), 16) % self._dim
            vec[h] += 1.0

        for i in range(len(text) - 2):
            gram = text[i:i + 3]
            h = int(hashlib.md5(gram.encode('utf-8') + b"_3").hexdigest(), 16) % self._dim
            vec[h] += 1.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0
        return vec

    def embed_documents(self, texts: List[str]) -> List[np.ndarray]:
        return [self._embed_single(t) for t in texts]

    def embed_query(self, query: str) -> np.ndarray:
        return self._embed_single(query)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """
    Google Gemini Embedding Adapter for gemini-embedding-001 or gemini-embedding-2.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-embedding-001",
        dimension: int = 768
    ):
        self._api_key = api_key
        self._model_name = model_name
        self._dim = dimension

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dim

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        key, _ = KeyManager.get_active_key()
        if not key:
            raise PermissionError("Gemini API 키가 설정되지 않았습니다.")
        return key

    def embed_documents(self, texts: List[str]) -> List[np.ndarray]:
        return [self._embed_single_api(t, task_type="RETRIEVAL_DOCUMENT") for t in texts]

    def embed_query(self, query: str) -> np.ndarray:
        return self._embed_single_api(query, task_type="RETRIEVAL_QUERY")

    def _embed_single_api(self, text: str, task_type: str) -> np.ndarray:
        key = self._get_api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_name}:embedContent?key={key}"

        payload = {
            "model": f"models/{self._model_name}",
            "content": {
                "parts": [{"text": text}]
            },
            "taskType": task_type
        }
        if self._dim:
            payload["outputDimensionality"] = self._dim

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                values = data.get("embedding", {}).get("values", [])
                if not values:
                    raise ValueError("Gemini 임베딩 반환값이 비어 있습니다.")

                vec = np.array(values, dtype=np.float32)
                # Validation
                if np.isnan(vec).any() or np.isinf(vec).any():
                    raise ValueError("임베딩 벡터에 NaN 또는 Inf가 포함되어 있습니다.")

                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                return vec

        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise PermissionError(f"Gemini API 키 인증 오류: HTTP {e.code}")
            elif e.code == 429:
                raise urllib.error.HTTPError(url, 429, "Gemini API Rate Limit 초과", e.hdrs, e.fp)
            else:
                raise RuntimeError(f"Gemini Embedding API 오류: HTTP {e.code} - {e.reason}")
        except urllib.error.URLError as e:
            raise ConnectionError(f"Gemini API 연결 실패: {e.reason}")


def get_active_embedding_provider() -> BaseEmbeddingProvider:
    """Returns the unified active embedding provider for consistent indexing and retrieval across views."""
    key, _ = KeyManager.get_active_key()
    if key:
        return GeminiEmbeddingProvider(api_key=key)
    return MockEmbeddingProvider(dimension=128)

