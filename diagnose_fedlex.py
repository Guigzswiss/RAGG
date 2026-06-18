# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v6 - exploration libre du triple store Virtuoso.
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
"""
import urllib.request, urllib.parse, json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "gsass-rag/1.0"

def sparql(query, label=""):
    if label:
        print("--- " + label + " ---")
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(SPARQL, data=data, headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    rows = result["results"]["bindings"]
    print(str(len(rows)) + " resultat(s)")
    for row in rows:
        line = "  "
        for k, v in row.items():
            line += k + "=" + v["value"] + "  "
        print(line)
    print()
    return rows

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v6 - Exploration triple store")
print("=" * 60)
print()

# 1. Lister les graphes disponibles
sparql("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } } LIMIT 20",
       "1. Graphes disponibles")

# 2. Chercher des sujets contenant '642' dans leur URI
sparql("""SELECT DISTINCT ?s WHERE {
  ?s ?p ?o .
  FILTER(CONTAINS(str(?s), "642"))
} LIMIT 20""", "2. URIs contenant '642'")

# 3. Chercher des sujets contenant 'taxonomy'
sparql("""SELECT DISTINCT ?s WHERE {
  ?s ?p ?o .
  FILTER(CONTAINS(str(?s), "taxonomy"))
} LIMIT 10""", "3. URIs contenant 'taxonomy'")

# 4. Chercher les proprietes jolux disponibles
sparql("""SELECT DISTINCT ?p WHERE {
  ?s ?p ?o .
  FILTER(CONTAINS(str(?p), "jolux"))
} LIMIT 30""", "4. Proprietes jolux utilisees")

# 5. Chercher toute ressource avec le mot 'LIFD' ou 'impot' dans un label
sparql("""SELECT ?s ?label WHERE {
  ?s ?p ?label .
  FILTER(isLiteral(?label) && CONTAINS(LCASE(str(?label)), "lifd"))
} LIMIT 10""", "5. Ressources avec label 'lifd'")

# 6. Echantillon des sujets dans le graphe par defaut
sparql("""SELECT DISTINCT ?type WHERE {
  ?s a ?type
} LIMIT 20""", "6. Types d'objets presents")

print("=" * 60)
print("  FIN v6")
print("=" * 60)
