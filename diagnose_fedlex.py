# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex - a lancer sur ta machine Windows AVANT l'indexation.
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
Puis ouvre diag_output.txt et copie le contenu dans le chat.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import sys
import io

# Forcer UTF-8 pour la sortie (evite les erreurs cp1252 sur Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SR = "642.11"
SPARQL_ENDPOINT = "https://fedlex.admin.ch/sparqlendpoint"
# URL XML connue de la LIFD (utilisee si SPARQL echoue)
FALLBACK_URI = "https://fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr"

def section(title):
    print()
    print("=" * 60)
    print("  " + title)
    print("=" * 60)

# ── 1. SPARQL (POST) ──────────────────────────────────────────────────────────
section("1. REQUETE SPARQL (POST)")

query = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX schema: <http://schema.org/>
SELECT ?expression ?title WHERE {
  ?work jolux:classifiedByTaxonomyEntry <https://fedlex.admin.ch/vocabulary/legal-taxonomy/642.11> ;
        jolux:hasExpression ?expression .
  ?expression jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
              schema:name ?title .
}
LIMIT 5
"""

post_data = urllib.parse.urlencode({"query": query}).encode("utf-8")
expression_uri = None

try:
    req = urllib.request.Request(
        SPARQL_ENDPOINT,
        data=post_data,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "gsass-rag-diagnostic/1.0",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    print("HTTP OK - " + str(len(raw)) + " octets recus")
    print("Debut reponse : " + raw[:200].decode("utf-8", errors="replace"))
    data = json.loads(raw)
    bindings = data.get("results", {}).get("bindings", [])
    print("JSON parse - " + str(len(bindings)) + " resultat(s)")
    for i, b in enumerate(bindings):
        expr = b.get("expression", {}).get("value", "?")
        title = b.get("title", {}).get("value", "?")
        print("  [" + str(i) + "] expression : " + expr)
        print("       title      : " + title)
    if bindings:
        expression_uri = bindings[0]["expression"]["value"]
except urllib.error.HTTPError as e:
    body = e.read(300).decode("utf-8", errors="replace")
    print("ERREUR HTTP " + str(e.code) + " : " + str(e.reason))
    print("Corps : " + body)
except Exception as e:
    print("ERREUR : " + str(e))

if not expression_uri:
    print("\nSPARQL echoue - utilisation de l'URI de secours...")
    expression_uri = FALLBACK_URI
    print("URI : " + expression_uri)

# ── 2. URL XML ────────────────────────────────────────────────────────────────
section("2. URL DU XML AKOMA NTOSO")

candidates = [
    expression_uri.replace("/eli/", "/filestore/fedlex.data.admin.ch/eli/") + "/akn/fr/xml",
    expression_uri + "/akn/fr/xml",
]

print("Expression URI : " + expression_uri)
print()
working_url = None
for i, candidate in enumerate(candidates):
    print("Candidat " + str(i+1) + " : " + candidate)
    try:
        req = urllib.request.Request(candidate, headers={
            "Accept": "application/xml, text/xml, */*",
            "User-Agent": "gsass-rag-diagnostic/1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            first_bytes = resp.read(500).decode("utf-8", errors="replace")
        print("  OK! Debut du contenu :")
        print("    " + first_bytes[:300])
        working_url = candidate
        break
    except urllib.error.HTTPError as e:
        print("  HTTP " + str(e.code) + " " + str(e.reason))
    except Exception as e:
        print("  ERREUR : " + str(e))

if not working_url:
    print("\nAucun URL XML ne fonctionne.")
    sys.exit(1)

# ── 3. Structure XML ──────────────────────────────────────────────────────────
section("3. STRUCTURE XML (50 premieres lignes)")

try:
    req = urllib.request.Request(working_url, headers={
        "Accept": "application/xml, text/xml, */*",
        "User-Agent": "gsass-rag-diagnostic/1.0",
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        xml_content = resp.read().decode("utf-8", errors="replace")

    lines = xml_content.splitlines()
    print("Taille : " + str(len(xml_content)) + " caracteres, " + str(len(lines)) + " lignes")
    print()
    print("--- DEBUT XML ---")
    for line in lines[:50]:
        print(line)
    print("--- FIN (50 premieres lignes) ---")

    # Namespaces et articles
    section("4. ELEMENTS 'article'")
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_content)

    ns_found = set()
    for elem in root.iter():
        if elem.tag.startswith("{"):
            ns = elem.tag.split("}")[0][1:]
            ns_found.add(ns)
    print("Namespaces :")
    for ns in sorted(ns_found):
        print("  " + ns)

    article_count = 0
    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local == "article":
            article_count += 1
            if article_count <= 3:
                print("\nArticle #" + str(article_count) + " :")
                print("  tag  : " + elem.tag)
                print("  eId  : " + str(elem.get("eId", "ABSENT")))
                print("  id   : " + str(elem.get("id", "ABSENT")))
                text = " ".join(elem.itertext())[:300]
                print("  texte: " + text)

    print("\nTotal elements 'article' : " + str(article_count))

except Exception as e:
    print("ERREUR parsing XML : " + str(e))

print()
print("=" * 60)
print("  DIAGNOSTIC TERMINE - copie diag_output.txt dans le chat")
print("=" * 60)
