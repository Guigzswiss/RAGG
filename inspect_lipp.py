"""
Inspecte le découpage réel de la LIPP (D 3 08) depuis ge.ch :
 - liste les article_id (pour voir comment art. 59 est nommé)
 - trouve le(s) chunk(s) contenant le barème fortune (« 111 059 »)

Lecture seule / réseau seulement — n'écrit RIEN.
"""
from canton_ge import fetch_law_from_ge

chunks = fetch_law_from_ge("D 3 08")
print(f"\nTotal : {len(chunks)} articles\n")

# Tous les article_id contenant 58, 59, 60
print("Articles 58–61 :")
for c in chunks:
    if any(n in c.article_id for n in ("58", "59", "60", "61")):
        print(f"  [{c.article_id}]  ({len(c.text)} car.)  {c.text[:60]}…")

# Le barème fortune où qu'il soit
print("\nChunk(s) contenant le barème « 111 059 » :")
found = False
for c in chunks:
    if "111 059" in c.text or "111059" in c.text:
        found = True
        print(f"\n  article_id : {c.article_id}")
        print(f"  longueur   : {len(c.text)} car.")
        print(f"  texte      :\n{c.text[:600]}")
if not found:
    print("  ⚠️ AUCUN chunk ne contient '111 059' — le tableau est peut-être")
    print("     mal parsé ou dans un autre article. À investiguer.")
