"""
Test objectif de l'encodage ge.ch : compte les caractères de remplacement
'�' (U+FFFD) sur toutes les lois. Zéro = encodage propre.

Lecture seule / réseau seulement — n'écrit RIEN.
"""
from canton_ge import fetch_law_from_ge, LOIS_GE

REPL = "�"  # caractère de remplacement �
total_bad = 0

for ref, name in LOIS_GE.items():
    try:
        chunks = fetch_law_from_ge(ref)
    except Exception as e:
        print(f"  ✗ {ref} {name}: {e}")
        continue
    bad = sum(c.text.count(REPL) for c in chunks)
    total_bad += bad
    flag = "  ⚠️" if bad else "  ✓"
    print(f"{flag} {ref:8s} {name:9s} : {len(chunks):3d} art., {bad} car. cassés")

print("\n" + "=" * 60)
print(f"TOTAL caractères cassés '�' : {total_bad}")
print("→ propre" if total_bad == 0 else "→ ENCORE un problème d'encodage")

# Affiche l'art. 59 de la LIPP en clair
print("\n" + "=" * 60)
print("LIPP art. 59 (vérif visuelle des accents) :\n")
for c in fetch_law_from_ge("D 3 08"):
    if c.article_id == "art. 59":
        print(repr(c.text[:300]))
        print()
        print(c.text[:300])
        break
