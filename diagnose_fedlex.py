# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v7 - bon domaine fedlex.data.admin.ch, cherche RS/CC.
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
"""
import urllib.request, urllib.parse, json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "gsass-rag/1.0"

def sparql(query, label="", timeout=25):
    if label:
        print("--- " + label + " ---")
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(SPARQL, data=data, headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())
        rows = result["results"]["bindings"]
        print(str(len(rows)) + " resultat(s)")
        for row in rows[:10]:
            line = "  "
            for k, v in row.items():
                val = v["value"]
                if len(val) > 100:
                    val = val[:100] + "..."
                line += k + "=" + val + "  "
            print(line)
        print()
        return rows
    except Exception as e:
        print("ERREUR: " + str(e))
        print()
        return []

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v7")
print("=" * 60)
print()

# 1. Chercher les graphes CC (Recueil systematique)
sparql("""SELECT DISTINCT ?g WHERE {
  GRAPH ?g { ?s ?p ?o }
  FILTER(CONTAINS(str(?g), "/cc/"))
} LIMIT 10""", "1. Graphes CC (Recueil systematique)")

# 2. Essayer le bon domaine pour la taxonomy 642.11
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?work ?expr WHERE {
  ?work jolux:classifiedByTaxonomyEntry
        <https://fedlex.data.admin.ch/vocabulary/legal-taxonomy/642.11> ;
        jolux:hasExpression ?expr .
} LIMIT 5""", "2. LIFD avec domaine fedlex.data.admin.ch")

# 3. Chercher la taxonomy par SR number comme literal
sparql("""SELECT ?s ?p ?o WHERE {
  ?s ?p "642.11"
} LIMIT 10""", "3. Ressources avec literal '642.11'")

# 4. Chercher la taxonomy par SR number dans URI
sparql("""SELECT DISTINCT ?tax WHERE {
  ?tax a ?type .
  FILTER(CONTAINS(str(?tax), "/642") && CONTAINS(str(?tax), "taxonomy"))
} LIMIT 10""", "4. Taxonomy URI contenant /642")

# 5. Chercher un work CC qui ressemble a la LIFD
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?work ?tax WHERE {
  GRAPH ?g {
    ?work jolux:classifiedByTaxonomyEntry ?tax .
    FILTER(CONTAINS(str(?g), "/cc/"))
  }
} LIMIT 10""", "5. Works CC avec leur taxonomy entry")

# 6. Explorer un graphe CC concret (s'il en existe)
sparql("""SELECT ?s ?p ?o WHERE {
  GRAPH <https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/graph> {
    ?s ?p ?o
  }
} LIMIT 15""", "6. Contenu du graphe LIFD direct")

# 7. Chercher des expressions directement par URI connue
sparql("""SELECT ?p ?o WHERE {
  <https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/fr> ?p ?o
} LIMIT 20""", "7. Proprietes de l'expression LIFD/FR")

# 8. Essayer l'URI expression sans /fr
sparql("""SELECT ?p ?o WHERE {
  <https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184> ?p ?o
} LIMIT 20""", "8. Proprietes du work LIFD")

print("=" * 60)
print("  FIN v7")
print("=" * 60)
