# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v9 - dates reelles + explorer les manifestations versionnees.
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

def try_dl(url, timeout=20):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/xml,*/*", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(500)
            ct = r.headers.get("Content-Type", "?")
        txt = body.decode("utf-8", errors="replace")
        is_xml = "<?xml" in txt or "<akomaNtoso" in txt or "<akn:" in txt
        return is_xml, ct, txt
    except urllib.error.HTTPError as e:
        return None, str(e.code), ""
    except Exception as e:
        return None, str(e), ""

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v9")
print("=" * 60)
print()

# 1. Toutes les versions datees de la LIFD (tri desc)
rows = sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?version WHERE {
  ?version jolux:isMemberOf <""" + BASE + """> .
} ORDER BY DESC(?version) LIMIT 20""", "1. Toutes versions datees LIFD (tri desc)")

dates = []
for row in rows:
    uri = row.get("version", {}).get("value", "")
    if uri:
        dates.append(uri.split("/")[-1])

print("Dates extraites: " + str(dates))
print()

# 2. Explorer une version recente - toutes ses proprietes
if dates:
    most_recent = dates[0]
    version_uri = BASE + "/" + most_recent
    sparql("""SELECT ?p ?o WHERE {
  GRAPH <""" + version_uri + """/graph> {
    <""" + version_uri + """> ?p ?o
  }
} LIMIT 30""", "2. Proprietes de la version " + most_recent)

    # 3. L'expression FR de cette version
    expr_fr = version_uri + "/fr"
    sparql("SELECT ?p ?o WHERE { <" + expr_fr + "> ?p ?o } LIMIT 20",
           "3. Expression FR de la version")

    # 4. Les manifestations de cette expression versionnee
    rows4 = sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?manif ?p ?o WHERE {
  <""" + expr_fr + """> jolux:hasManifestation ?manif .
  ?manif ?p ?o .
} LIMIT 30""", "4. Manifestations de l'expression versionnee FR")

    # 5. Si on a des manifestations, chercher les URLs de fichier
    if rows4:
        manif_uris = list(set(r["manif"]["value"] for r in rows4))
        print("Manifestations trouvees: " + str(manif_uris))
        print()
        for m in manif_uris[:3]:
            sparql("SELECT ?p ?o WHERE { <" + m + "> ?p ?o } LIMIT 20",
                   "5. Proprietes de la manifestation " + m.split("/")[-1])

# 6. Tester les URLs XML avec les vraies dates
print("--- 6. Telechargement XML avec vraies dates ---")
print()
for d in dates[:8]:
    url = BASE + "/" + d + "/fr/akn/fr/xml"
    ok, ct, txt = try_dl(url)
    if ok:
        print("  " + d + " => XML! CT=" + ct)
        print("  DEBUT: " + txt[:200])
        print("  *** URL TROUVEE: " + url + " ***")
        print()
        break
    else:
        print("  " + d + " => " + ct)

# 7. Chercher isExemplifiedBy sur toutes versions
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?version ?expr ?manif ?url WHERE {
  ?version jolux:isMemberOf <""" + BASE + """> ;
           jolux:isRealizedBy ?expr .
  ?expr jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
        jolux:hasManifestation ?manif .
  ?manif jolux:isExemplifiedBy ?url .
} ORDER BY DESC(?version) LIMIT 10""", "7. isExemplifiedBy sur versions datees")

print()
print("=" * 60)
print("  FIN v9")
print("=" * 60)
