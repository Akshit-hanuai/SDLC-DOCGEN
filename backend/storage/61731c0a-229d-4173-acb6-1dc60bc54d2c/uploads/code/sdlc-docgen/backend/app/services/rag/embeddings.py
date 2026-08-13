import hashlib
import re
from functools import lru_cache

import numpy as np

from app.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


class Embedder:
    dim: int = settings.embedding_dim

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(settings.embedding_model)
        self._st_dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return _project_dim(np.asarray(vectors, dtype=np.float64), self.dim)


class HashEmbedder(Embedder):
    def embed(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dim), dtype=np.float64)
        for i, text in enumerate(texts):
            for token in _TOKEN_RE.findall(text.lower()):
                digest = hashlib.md5(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "little") % self.dim
                sign = 1.0 if digest[4] % 2 else -1.0
                matrix[i, idx] += sign
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    try:
        import sentence_transformers  # noqa: F401

        return SentenceTransformerEmbedder()
    except Exception:
        return HashEmbedder()


def _project_dim(vectors: np.ndarray, dim: int) -> np.ndarray:
    if vectors.shape[1] == dim:
        return vectors
    if vectors.shape[1] > dim:
        return vectors[:, :dim]
    padded = np.zeros((vectors.shape[0], dim), dtype=np.float64)
    padded[:, : vectors.shape[1]] = vectors
    norms = np.linalg.norm(padded, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return padded / norms
