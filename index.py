"""
Index hybride : ChromaDB (dense) + BM25 (sparse), fusion RRF.
"""
from __future__ import annotations
from typing import List, Tuple, Dict, Any
import json
import math

from parse_chunk import ArticleChunk


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank + 1)


class HybridIndex:
    """
    Combine ChromaDB (recherche dense) et BM25 (recherche lexicale) via RRF.
    """

    def __init__(self, embedder, chroma_dir: str, collection_name: str):
        import chromadb

        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._bm25 = None  # initialisé à la première requête

    # ── Indexation ────────────────────────────────────────────────────────────

    def add_chunks(self, chunks: List[ArticleChunk]) -> None:
        if not chunks:
            return
        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed(texts)
        ids = [f"{c.law_sr}_{c.article_id}_{i}" for i, c in enumerate(chunks)]
        metadatas = [
            {
                "law_sr": c.law_sr,
                "law_name": c.law_name,
                "article_id": c.article_id,
                "url": c.url,
                "version_date": c.version_date,
            }
            for c in chunks
        ]
        self.collection.upsert(ids=ids, embeddings=embeddings,
                               documents=texts, metadatas=metadatas)
        self._bm25 = None  # invalider le cache BM25

    # ── BM25 interne ─────────────────────────────────────────────────────────

    def _get_bm25(self):
        if self._bm25 is not None:
            return self._bm25
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return None
        result = self.collection.get(include=["documents", "metadatas"])
        docs = result.get("documents") or []
        if not docs:
            return None
        tokenized = [d.lower().split() for d in docs]
        self._bm25 = (BM25Okapi(tokenized), docs, result.get("metadatas", []), result.get("ids", []))
        return self._bm25

    # ── Recherche hybride ────────────────────────────────────────────────────

    def search(self, query: str, top_k_dense: int = 10,
               top_k_bm25: int = 10, top_k_final: int = 5,
               rrf_k: int = 60) -> List[Dict[str, Any]]:

        query_vec = self.embedder.embed_one(query)

        # Dense
        dense_result = self.collection.query(
            query_embeddings=[query_vec],
            n_results=min(top_k_dense, self.collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        dense_docs = dense_result["documents"][0] if dense_result["documents"] else []
        dense_metas = dense_result["metadatas"][0] if dense_result["metadatas"] else []

        scores: Dict[str, float] = {}
        doc_store: Dict[str, Tuple[str, dict]] = {}

        for rank, (doc, meta) in enumerate(zip(dense_docs, dense_metas)):
            key = f"{meta.get('law_sr')}_{meta.get('article_id')}"
            scores[key] = scores.get(key, 0.0) + _rrf_score(rank, rrf_k)
            doc_store[key] = (doc, meta)

        # BM25
        bm25_data = self._get_bm25()
        if bm25_data:
            bm25_model, docs, metas, ids = bm25_data
            bm25_scores = bm25_model.get_scores(query.lower().split())
            ranked = sorted(range(len(docs)), key=lambda i: bm25_scores[i], reverse=True)[:top_k_bm25]
            for rank, idx in enumerate(ranked):
                meta = metas[idx] if idx < len(metas) else {}
                key = f"{meta.get('law_sr')}_{meta.get('article_id')}"
                scores[key] = scores.get(key, 0.0) + _rrf_score(rank, rrf_k)
                if key not in doc_store:
                    doc_store[key] = (docs[idx], meta)

        # Trier et retourner
        sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)[:top_k_final]
        return [{"text": doc_store[k][0], "metadata": doc_store[k][1], "score": scores[k]}
                for k in sorted_keys if k in doc_store]

    def count(self) -> int:
        return self.collection.count()
