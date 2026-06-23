"""
Diagnostic : combien de chunks sont mal classés à cause des PDF SILGENEVE
qui regroupent plusieurs lois ?

Chaque page SILGENEVE contient un pied de page "rsGE <REF>: <nom>".
On compare cette VRAIE référence avec le law_sr stocké.

Lecture seule, ne modifie rien.
"""
from config import CHROMA_DIR, COLLECTION_NAME
import chromadb
import re

client = chromadb.PersistentClient(path=CHROMA_DIR)
col = client.get_collection(COLLECTION_NAME)

# Pied de page SILGENEVE : "rsGE D 3 17: Loi de procédure fiscale (LPFisc)"
RSGE_RE = re.compile(r"rsGE\s+([A-Z])\s*(\d+)\s+(\d+)\s*:", re.IGNORECASE)

res = col.get(include=["documents", "metadatas"])
ids = res.get("ids") or []
docs = res.get("documents") or []
metas = res.get("metadatas") or []

print(f"Collection : {COLLECTION_NAME} — {len(ids)} chunks\n")
print("=" * 70)

# 1) Mismatch : law_sr stocké != référence du pied de page
mismatches = {}   # (stored, true) -> count
mismatch_examples = {}
no_footer = 0
footer_ok = 0

for i, _id in enumerate(ids):
    txt = docs[i] or ""
    m = RSGE_RE.search(txt)
    if not m:
        no_footer += 1
        continue
    true_ref = f"{m.group(1).upper()} {m.group(2)} {m.group(3)}"
    stored = (metas[i] or {}).get("law_sr", "")
    if stored == true_ref:
        footer_ok += 1
    else:
        key = (stored, true_ref)
        mismatches[key] = mismatches.get(key, 0) + 1
        if key not in mismatch_examples:
            art = (metas[i] or {}).get("article_id")
            mismatch_examples[key] = f"{_id}  (art={art})  «{txt[:70]}…»"

print(f"\n[1] Chunks avec pied de page SILGENEVE concordant : {footer_ok}")
print(f"    Chunks sans pied de page (autres sources)      : {no_footer}")
print(f"    Chunks MAL CLASSÉS (footer != law_sr)          : {sum(mismatches.values())}\n")

if mismatches:
    print("    Détail (law_sr stocké  →  vraie réf  : nombre) :")
    for (stored, true_ref), n in sorted(mismatches.items(), key=lambda x: -x[1]):
        print(f"      {stored:12s} → {true_ref:12s} : {n:4d}")
        print(f"          ex. {mismatch_examples[(stored, true_ref)]}")

# 2) Le chunk périmé (vieux barème fortune) en détail
print("\n" + "=" * 70)
print("\n[2] Chunk(s) avec le VIEUX barème fortune (0,24 / 30'000)\n")
for i, _id in enumerate(ids):
    txt = docs[i] or ""
    if "0,24" in txt and ("30'000" in txt or "30 000" in txt):
        m = metas[i] or {}
        foot = RSGE_RE.search(txt)
        print(f"  ID       : {_id}")
        print(f"  law_sr   : {m.get('law_sr')}  /  {m.get('article_id')}")
        print(f"  footer   : {foot.group(0) if foot else '(aucun pied de page SILGENEVE)'}")
        print(f"  longueur : {len(txt)} car.")
        print(f"  texte    : {txt[:300]}…\n")
