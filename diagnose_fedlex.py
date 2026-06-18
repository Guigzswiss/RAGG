# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v8 - trouve les versions datees et l'URL XML reelle.
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
"""
import urllib.request, urllib.parse, json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "gsass-rag/1.0"
BASE = "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184"

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
        for row in rows[:15]:
            line = "  "
            for k, v in row.items():
                val = v["value"]
                if len(val) > 120:
                    val = val[:120] + "..."
                line += k + "=" + val + "  "
            print(line)
        print()
        return rows
    except Exception as e:
        print("ERREUR: " + str(e))
        print()
        return []

def try_download(url, label=""):
    print("  [" + label + "] " + url)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/xml,*/*", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(600)
            ct = r.headers.get("Content-Type", "?")
        txt = body.decode("utf-8", errors="replace")
        is_xml = "<?xml" in txt or "<akomaNtoso" in txt or "<akn:" in txt
        print("    CT=" + ct + " XML=" + str(is_xml))
        if is_xml:
            print("    DEBUT XML: " + txt[:300])
        else:
            print("    (HTML ou autre) debut: " + txt[:100])
        print()
        return is_xml, txt
    except urllib.error.HTTPError as e:
        print("    HTTP " + str(e.code))
        print()
        return False, None
    except Exception as e:
        print("    ERR: " + str(e))
        print()
        return False, None

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v8 - Versions datees LIFD")
print("=" * 60)
print()

# 1. Trouver les consolidations (versions datees) du work LIFD
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?consol ?date WHERE {
  GRAPH ?g {
    ?consol jolux:isRealizedBy <""" + BASE + """/fr> .
  }
  OPTIONAL { ?consol jolux:dateDocument ?date }
} LIMIT 10""", "1. Consolidations avec jolux:isRealizedBy")

# 2. Chercher ce qui pointe vers le work LIFD
sparql("""SELECT ?s ?p WHERE {
  GRAPH ?g {
    ?s ?p <""" + BASE + """> .
  }
} LIMIT 10""", "2. Qui pointe vers le work LIFD")

# 3. Toutes les proprietes du work dans son graphe
sparql("""SELECT ?p ?o WHERE {
  GRAPH <""" + BASE + """/graph> {
    <""" + BASE + """> ?p ?o
  }
} LIMIT 20""", "3. Proprietes du work dans son propre graphe")

# 4. Chercher par historicalLegalId les versions datees
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT DISTINCT ?expr ?date WHERE {
  ?expr jolux:historicalLegalId "642.11" ;
        jolux:language <http://publications.europa.eu/resource/authority/language/FRA> .
  OPTIONAL { ?expr jolux:dateDocument ?date }
} LIMIT 10""", "4. Toutes expressions FR avec SR 642.11")

# 5. Chercher les manifestations de l'expression de base
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?manif ?p ?val WHERE {
  <""" + BASE + """/fr> jolux:hasManifestation ?manif .
  ?manif ?p ?val .
} LIMIT 20""", "5. Manifestations de l'expression de base")

# 6. Tenter des URLs XML avec dates connues
print("--- 6. Tentative telechargement XML avec dates ---")
print()
dates = ["20250101", "20240101", "20230101", "20220101", "20210101"]
xml_found = None
for d in dates:
    url = BASE + "/" + d + "/fr/akn/fr/xml"
    ok, content = try_download(url, d)
    if ok:
        xml_found = (url, content)
        break

# 7. Si aucune date directe, essayer via SPARQL les manifestations versionnees
if not xml_found:
    print("--- 7. SPARQL: chercher isExemplifiedBy sur toutes versions ---")
    rows = sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?expr ?manif ?url WHERE {
  ?expr jolux:historicalLegalId "642.11" ;
        jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
        jolux:hasManifestation ?manif .
  ?manif jolux:isExemplifiedBy ?url .
} LIMIT 10""", "7a. Manifestations avec isExemplifiedBy")

    if rows:
        for row in rows[:3]:
            url = row.get("url", {}).get("value", "")
            if url:
                ok, content = try_download(url, "URL depuis SPARQL")
                if ok:
                    xml_found = (url, content)
                    break

if xml_found:
    print("*** URL XML TROUVEE: " + xml_found[0] + " ***")
else:
    print("Aucun fichier XML accessible - voir resultats SPARQL ci-dessus")

print()
print("=" * 60)
print("  FIN v8")
print("=" * 60)
