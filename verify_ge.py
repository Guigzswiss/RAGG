"""
Vérification : le parser ge.ch/legi récupère-t-il bien les lois cantonales,
en version ACTUELLE, avant de toucher à la base ?

Lecture seule / réseau seulement — n'écrit RIEN dans ChromaDB.

Usage : python verify_ge.py
"""
from canton_ge import fetch_law_from_ge, LOIS_GE

print("=" * 70)
print("Test d'accès et de parsing ge.ch/legi (aucune écriture en base)\n")

summary = []
for ref, name in LOIS_GE.items():
    print("-" * 70)
    try:
        chunks = fetch_law_from_ge(ref)
        n = len(chunks)
        print(f"  → {n} articles extraits")
        summary.append((ref, name, n, "OK" if n >= 3 else "PEU"))
        # Montre l'art. 59 pour la LIPP (le barème fortune)
        if ref == "D 3 08":
            for c in chunks:
                if c.article_id == "art. 59":
                    print(f"\n  *** LIPP art. 59 (doit montrer 1,49‰ … 3,83‰) ***")
                    print(f"  {c.text[:350]}\n")
    except Exception as e:
        print(f"  ✗ ÉCHEC : {e}")
        summary.append((ref, name, 0, "ÉCHEC"))

print("=" * 70)
print("\nRÉSUMÉ :")
for ref, name, n, status in summary:
    print(f"  {status:6s}  {ref:8s} {name:9s} : {n} articles")

ok = sum(1 for *_, s in summary if s == "OK")
print(f"\n{ok}/{len(summary)} lois récupérées correctement.")
if ok == len(summary):
    print("→ Tout est bon : on peut faire le re-index propre.")
else:
    print("→ Certaines lois échouent : ne pas re-indexer encore, dis-le moi.")
