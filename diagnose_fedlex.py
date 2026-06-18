# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v5 - trouve l'URL reelle du fichier XML via SPARQL Virtuoso.
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
"""
import urllib.request, urllib.parse, urllib.error, json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "gsass-rag/1.0"

def sparql(query):
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(SPARQL, data=data, headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v5 - Exploration RDF")
print("=" * 60)

# ── 1. Trouver les expressions de la LIFD (SR 642.11) ─────────────────────────
print()
print("--- 1. Expressions LIFD ---")
q1 = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX schema: <http://schema.org/>
SELECT ?work ?expr ?title WHERE {
  ?work jolux:classifiedByTaxonomyEntry
        <https://fedlex.admin.ch/vocabulary/legal-taxonomy/642.11> ;
        jolux:hasExpression ?expr .
  ?expr jolux:language
        <http://publications.europa.eu/resource/authority/language/FRA> ;
        schema:name ?title .
}
LIMIT 5
"""
r1 = sparql(q1)
bindings = r1["results"]["bindings"]
print(str(len(bindings)) + " expression(s):")
for b in bindings:
    print("  work : " + b.get("work",{}).get("value","?"))
    print("  expr : " + b.get("expr",{}).get("value","?"))
    print("  title: " + b.get("title",{}).get("value","?"))
    print()

if not bindings:
    print("Aucune expression - arret.")
    sys.exit(1)

expr_uri = bindings[0]["expr"]["value"]
print("Expression retenue: " + expr_uri)

# ── 2. Trouver les manifestations de cette expression ─────────────────────────
print()
print("--- 2. Manifestations ---")
q2 = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?manif ?format ?url WHERE {
  <""" + expr_uri + """> jolux:hasManifestation ?manif .
  OPTIONAL { ?manif jolux:userFormat ?format }
  OPTIONAL { ?manif jolux:isExemplifiedBy ?url }
}
"""
r2 = sparql(q2)
manifests = r2["results"]["bindings"]
print(str(len(manifests)) + " manifestation(s):")
for m in manifests:
    fmt = m.get("format",{}).get("value","?")
    url = m.get("url",{}).get("value","?")
    manif = m.get("manif",{}).get("value","?")
    print("  format: " + fmt)
    print("  url   : " + url)
    print("  manif : " + manif)
    print()

# ── 3. Explorer toutes les proprietes d'une manifestation ─────────────────────
print()
print("--- 3. Toutes les proprietes de la 1ere manifestation ---")
if manifests:
    manif_uri = manifests[0]["manif"]["value"]
    q3 = "SELECT ?p ?o WHERE { <" + manif_uri + "> ?p ?o }"
    r3 = sparql(q3)
    for b in r3["results"]["bindings"]:
        print("  " + b["p"]["value"].split("/")[-1].split("#")[-1] + " = " + b["o"]["value"])

# ── 4. Chercher directement les URLs de fichiers XML ──────────────────────────
print()
print("--- 4. Recherche directe des URLs XML ---")
q4 = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?manif ?p ?url WHERE {
  <""" + expr_uri + """> jolux:hasManifestation ?manif .
  ?manif ?p ?url .
  FILTER(isIRI(?url) && (
    CONTAINS(str(?url), "xml") ||
    CONTAINS(str(?url), "akn") ||
    CONTAINS(str(?url), "filestore")
  ))
}
"""
r4 = sparql(q4)
print(str(len(r4["results"]["bindings"])) + " URL(s) avec xml/akn/filestore:")
for b in r4["results"]["bindings"]:
    print("  prop: " + b["p"]["value"].split("#")[-1])
    print("  url : " + b["url"]["value"])
    print()

# ── 5. Tester le telechargement de la premiere URL XML trouvee ────────────────
xml_url = None
for b in r4["results"]["bindings"]:
    u = b["url"]["value"]
    if "xml" in u.lower() or "akn" in u.lower():
        xml_url = u
        break

if xml_url:
    print("--- 5. Tentative de telechargement ---")
    print("URL: " + xml_url)
    try:
        req = urllib.request.Request(xml_url, headers={
            "Accept": "application/xml, */*",
            "User-Agent": UA
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(500)
            ct = r.headers.get("Content-Type","?")
        txt = body.decode("utf-8", errors="replace")
        is_xml = "<?xml" in txt or "<akn" in txt or "<akomaNtoso" in txt
        print("CT: " + ct)
        print("XML detecte: " + str(is_xml))
        print("Debut: " + txt[:300])
    except Exception as e:
        print("ERREUR: " + str(e))

print()
print("=" * 60)
print("  FIN v5")
print("=" * 60)
