"""
Diagnostic : que contient RÉELLEMENT l'index pour la LIPP art. 59 ?

Compare le texte indexé avec le barème affiché dans la réponse du RAG.
On cherche à savoir si :
  (a) le chunk indexé est périmé (vieux barème), ou
  (b) le modèle a halluciné / pris les chiffres ailleurs.

Lecture seule, ne modifie rien.
"""
from config import CHROMA_DIR, COLLECTION_NAME
import chromadb

client = chromadb.PersistentClient(path=CHROMA_DIR)
col = client.get_collection(COLLECTION_NAME)

print(f"Collection : {COLLECTION_NAME} — {col.count()} chunks\n")
print("=" * 70)

# 1) Tous les chunks de la LIPP (D 3 08), articles autour de 59
print("\n[1] Chunks LIPP (law_sr='D 3 08') art. 59 / 15 / 60\n")
res = col.get(
    where={"law_sr": {"$eq": "D 3 08"}},
    include=["documents", "metadatas"],
)
ids = res.get("ids") or []
docs = res.get("documents") or []
metas = res.get("metadatas") or []
print(f"  Total chunks D 3 08 : {len(ids)}")

targets = {"art. 59", "art. 15", "art. 60"}
for i, _id in enumerate(ids):
    m = metas[i] or {}
    art = (m.get("article_id") or "").strip().lower()
    if art in targets:
        print("\n" + "-" * 70)
        print(f"  ID        : {_id}")
        print(f"  law_name  : {m.get('law_name')}")
        print(f"  article   : {m.get('article_id')}")
        print(f"  version   : {m.get('version_date')}")
        print(f"  url       : {m.get('url')}")
        print(f"  --- TEXTE ({len(docs[i] or '')} car.) ---")
        print(docs[i])

# 2) Recherche du vieux barème (0,24‰ / 30 000 / 0,97) où qu'il soit
print("\n" + "=" * 70)
print("\n[2] Où apparaît le VIEUX barème (ex. '0,24' ou '0.24', '0,97') ?\n")
all_res = col.get(include=["documents", "metadatas"])
all_ids = all_res.get("ids") or []
all_docs = all_res.get("documents") or []
all_metas = all_res.get("metadatas") or []

needles = ["0,24", "0.24", "0,97", "0.97", "3,39", "3.39"]
hits = 0
for i, _id in enumerate(all_ids):
    txt = all_docs[i] or ""
    if any(n in txt for n in needles):
        hits += 1
        m = all_metas[i] or {}
        print(f"  • {m.get('law_name')} / {m.get('article_id')} (law_sr={m.get('law_sr')})  id={_id}")
        # montre l'extrait autour du premier needle
        for n in needles:
            pos = txt.find(n)
            if pos != -1:
                a = max(0, pos - 60)
                b = min(len(txt), pos + 60)
                print(f"      …{txt[a:b]}…")
                break
        if hits >= 20:
            print("  (… arrêt à 20 résultats)")
            break

if hits == 0:
    print("  Aucun chunk ne contient ce vieux barème.")
    print("  → Le modèle a probablement HALLUCINÉ les chiffres.")
