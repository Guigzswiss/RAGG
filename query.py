"""
Moteur RAG : retrieval + génération avec prompt anti-hallucination.
"""
from __future__ import annotations
from typing import List, Dict, Any

SYSTEM_PROMPT = """Tu es un assistant juridique et fiscal suisse expert, spécialisé dans le droit fédéral et cantonal suisse (Genève, Vaud).

RÈGLES ABSOLUES :
1. Réponds UNIQUEMENT en te basant sur les extraits de loi fournis ci-dessous.
2. Pour chaque affirmation, cite la source exacte : Loi (SR ou référence cantonale), numéro d'article.
3. Si les extraits ne contiennent pas la réponse, dis EXPLICITEMENT :
   "Je ne trouve pas de réponse dans les articles fournis."
4. N'invente JAMAIS de numéros d'articles, taux, montants ou règles absents des extraits.
5. Utilise un langage juridique précis et professionnel en français.

INSTRUCTIONS SPÉCIFIQUES :
- Si la question porte sur un taux d'imposition, cherche et cite le taux exact mentionné dans les extraits.
- Si la question porte sur une société (SA, Sàrl, etc.), distingue clairement impôt fédéral (LIFD) et cantonal (LIPM pour Genève, LI pour Vaud).
- Si la question porte sur une personne physique, distingue revenu et fortune, fédéral et cantonal.
- Cite toujours les alinéas précis (al. 1, al. 2, etc.) quand ils sont pertinents.
- Si plusieurs extraits se complètent, synthétise-les en indiquant chaque source.

FORMAT DE CITATION : (LIFD, art. X al. Y) ou (LIPM GE, art. X) ou (RS 642.11, art. X)"""


def build_context(results: List[Dict[str, Any]]) -> str:
    parts = []
    for r in results:
        meta = r["metadata"]
        law = meta.get("law_name", meta.get("law_sr", "?"))
        art = meta.get("article_id", "?")
        url = meta.get("url", "")
        parts.append(f"[{law}, {art}]\n{r['text']}\nSource: {url}")
    return "\n\n---\n\n".join(parts)


class RAGEngine:
    def __init__(self, index, chat_client, chat_model: str):
        self.index = index
        self.chat_client = chat_client
        self.chat_model = chat_model

    def ask(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        from config import TOP_K_DENSE, TOP_K_BM25, RRF_K

        results = self.index.search(
            question,
            top_k_dense=TOP_K_DENSE,
            top_k_bm25=TOP_K_BM25,
            top_k_final=top_k,
            rrf_k=RRF_K,
        )

        if not results:
            return {
                "answer": "Aucun document pertinent trouvé dans l'index.",
                "sources": [],
            }

        context = build_context(results)
        user_message = f"""Extraits de loi pertinents :

{context}

Question : {question}"""

        response = self.chat_client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1024,
        )

        answer = response.choices[0].message.content.strip()
        sources = [
            {
                "law": r["metadata"].get("law_name", r["metadata"].get("law_sr")),
                "article": r["metadata"].get("article_id"),
                "url": r["metadata"].get("url", ""),
            }
            for r in results
        ]

        return {"answer": answer, "sources": sources}
