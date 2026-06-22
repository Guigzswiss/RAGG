"""
Suppression ciblée du chunk AFC_NOTICE_DA-M mal classé comme LRCV (B 6 09),
puis ré-indexation avec la bonne identité.

Ne touche PAS aux vrais chunks LRCV.
"""
from config import CHROMA_DIR, COLLECTION_NAME
import chromadb

client = chromadb.PersistentClient(path=CHROMA_DIR)
col = client.get_collection(COLLECTION_NAME)

before = col.count()

res = col.get(
    where={"law_sr": {"$eq": "B 6 09"}},
    include=["documents", "metadatas"],
)
ids = res.get("ids") or []
docs = res.get("documents") or []
metas = res.get("metadatas") or []

print(f"Chunks avec law_sr='B 6 09' : {len(ids)}")

to_delete = []
for i, _id in enumerate(ids):
    text = (docs[i] or "")[:200]
    is_afc = (
        "administration fédérale" in text.lower()
        or "afc" in text.lower()
        or "AFC" in _id
        or "DA-M" in text.upper()
        or "double imposition" in text.lower()
    )
    marker = "  ✗ SUPPRIMER (notice AFC)" if is_afc else "  ✓ garder (vraie LRCV)"
    print(f"\n{marker}")
    print(f"  ID  : {_id}")
    print(f"  art : {(metas[i] or {}).get('article_id')}")
    print(f"  text: {text}...")
    if is_afc:
        to_delete.append(_id)

if not to_delete:
    print("\nAucun chunk AFC à supprimer. Rien à faire.")
else:
    col.delete(ids=to_delete)
    after = col.count()
    print(f"\nSupprimé : {len(to_delete)} chunk(s) de la notice AFC.")
    print(f"Total : {before} → {after} chunks.")
    print("Ré-indexe maintenant avec :")
    print("  python run.py index-pdf data\\notice_fix")
