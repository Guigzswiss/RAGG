"""
Diagnostic Fedlex — à lancer sur ta machine Windows AVANT l'indexation.
Lance : python diagnose_fedlex.py
Copie-colle la sortie complète dans le chat.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import sys

SR = "642.11"
SPARQL_ENDPOINT = "https://fedlex.admin.ch/sparqlendpoint"

def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

# ── 1. SPARQL ─────────────────────────────────────────────────────────────────
section("1. REQUÊTE SPARQL")

query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX schema: <http://schema.org/>
SELECT ?expression ?title WHERE {{
  ?work jolux:classifiedByTaxonomyEntry <https://fedlex.admin.ch/vocabulary/legal-taxonomy/{SR}> ;
        jolux:hasExpression ?expression .
  ?expression jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
              schema:name ?title .
}}
LIMIT 5
"""

params = urllib.parse.urlencode({
    "query": query,
    "format": "application/sparql-results+json"
})
url = f"{SPARQL_ENDPOINT}?{params}"
print(f"URL : {url[:120]}...")

try:
    req = urllib.request.Request(url, headers={
        "Accept": "application/sparql-results+json",
        "User-Agent": "gsass-rag-diagnostic/1.0"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    data = json.loads(raw)
    bindings = data.get("results", {}).get("bindings", [])
    print(f"OK — {len(bindings)} résultat(s)")
    for i, b in enumerate(bindings):
        expr = b.get("expression", {}).get("value", "?")
        title = b.get("title", {}).get("value", "?")
        print(f"  [{i}] expression : {expr}")
        print(f"       title      : {title}")
    expression_uri = bindings[0]["expression"]["value"] if bindings else None
except urllib.error.HTTPError as e:
    print(f"ERREUR HTTP {e.code} : {e.reason}")
    expression_uri = None
except Exception as e:
    print(f"ERREUR : {e}")
    expression_uri = None

if not expression_uri:
    print("\nSPARQL échoué — impossible de continuer.")
    sys.exit(1)

# ── 2. Construction de l'URL XML ──────────────────────────────────────────────
section("2. URL DU XML AKOMA NTOSO")

# Essayer plusieurs patterns d'URL
candidates = [
    # Pattern actuel dans fedlex.py
    expression_uri.replace("/eli/", "/filestore/fedlex.data.admin.ch/eli/") + "/akn/fr/xml",
    # Pattern alternatif direct
    expression_uri + "/akn/fr/xml",
    # Pattern filestore sans doublon
    "https://fedlex.admin.ch/filestore/" + expression_uri.replace("https://", "").replace("http://", "") + "/akn/fr/xml",
]

print(f"Expression URI : {expression_uri}")
print()
working_url = None
for i, candidate in enumerate(candidates):
    print(f"Candidat {i+1} : {candidate}")
    try:
        req = urllib.request.Request(candidate, headers={
            "Accept": "application/xml, text/xml, */*",
            "User-Agent": "gsass-rag-diagnostic/1.0"
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            first_bytes = resp.read(500).decode("utf-8", errors="replace")
        print(f"  → OK ! Début du contenu :")
        print(f"    {first_bytes[:200]}")
        working_url = candidate
        break
    except urllib.error.HTTPError as e:
        print(f"  → HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"  → ERREUR : {e}")

if not working_url:
    print("\nAucun URL XML ne fonctionne.")
    sys.exit(1)

# ── 3. Structure XML ──────────────────────────────────────────────────────────
section("3. STRUCTURE XML (100 premières lignes)")

try:
    req = urllib.request.Request(working_url, headers={
        "Accept": "application/xml, text/xml, */*",
        "User-Agent": "gsass-rag-diagnostic/1.0"
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        xml_content = resp.read().decode("utf-8", errors="replace")

    lines = xml_content.splitlines()
    print(f"Taille totale : {len(xml_content)} caractères, {len(lines)} lignes")
    print()
    print("--- DÉBUT XML ---")
    for line in lines[:100]:
        print(line)
    print("--- FIN (100 premières lignes) ---")

    # Chercher les articles
    section("4. RECHERCHE DES ÉLÉMENTS 'article'")
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_content)

    # Trouver tous les namespaces
    ns_found = set()
    for elem in root.iter():
        if elem.tag.startswith("{"):
            ns = elem.tag.split("}")[0][1:]
            ns_found.add(ns)
    print("Namespaces trouvés :")
    for ns in sorted(ns_found):
        print(f"  {ns}")

    # Chercher les articles
    article_count = 0
    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local == "article":
            article_count += 1
            if article_count <= 3:
                print(f"\nArticle #{article_count} :")
                print(f"  tag      : {elem.tag}")
                print(f"  eId      : {elem.get('eId', 'ABSENT')}")
                print(f"  id       : {elem.get('id', 'ABSENT')}")
                # Texte brut
                text = " ".join((elem.itertext()))[:300]
                print(f"  texte    : {text}")

    print(f"\nNombre total d'éléments 'article' : {article_count}")

except Exception as e:
    print(f"ERREUR parsing XML : {e}")

print()
print("=" * 60)
print("  DIAGNOSTIC TERMINÉ — copie toute cette sortie dans le chat")
print("=" * 60)
