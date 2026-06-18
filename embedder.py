"""
Client d'embedding : Infomaniak (prod) ou sentence-transformers (fallback hors-ligne).
"""
from __future__ import annotations
from typing import List
import os


class InfomaniakEmbedder:
    """Appelle l'API Infomaniak /embeddings (compatible OpenAI)."""

    def __init__(self, base_url: str, token: str, model: str):
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("pip install openai") from e
        self.client = OpenAI(api_key=token, base_url=base_url)
        self.model = model

    # bge_multilingual_gemma2 context window is 8192 tokens; truncate conservatively
    MAX_CHARS = 6000
    BATCH_SIZE = 32

    def _clean(self, text: str) -> str:
        # Strip null bytes and truncate
        text = text.replace("\x00", " ").strip()
        return text[: self.MAX_CHARS] if len(text) > self.MAX_CHARS else text

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        texts = [self._clean(t) for t in texts]
        results = []
        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i : i + self.BATCH_SIZE]
            response = self.client.embeddings.create(model=self.model, input=batch)
            results.extend(item.embedding for item in response.data)
        return results

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class LocalEmbedder:
    """Embedder hors-ligne pour les selftests (aucun appel réseau)."""

    def __init__(self):
        import hashlib, struct
        self._hash = hashlib.md5
        self.dim = 384

    def _vec(self, text: str):
        import hashlib, struct, math
        h = hashlib.sha256(text.encode()).digest()
        floats = [struct.unpack("f", h[i : i + 4])[0] for i in range(0, 32, 4)]
        # pad to dim
        while len(floats) < self.dim:
            floats.extend(floats[: self.dim - len(floats)])
        norm = math.sqrt(sum(x * x for x in floats)) or 1.0
        return [x / norm for x in floats[: self.dim]]

    def embed(self, texts):
        return [self._vec(t) for t in texts]

    def embed_one(self, text):
        return self._vec(text)
