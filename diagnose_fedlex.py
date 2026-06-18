# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v10 - isEmbodiedBy + /fr/xml (pas /akn/fr/xml).
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
"""
import urllib.request, urllib.parse, json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "gsass-rag/1.0"
BASE = "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184"
# Dates recentes connues (les plus recentes en vigueur)
DATES = ["20260101", "20250101", "20240516", "20240301", "20240101",
         "20230101", "20220101", "20210701"]

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

def try_dl(url, label="", timeout=20):
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/xml, text/xml, */*",
            "User-Agent": UA
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(800)
            ct = r.headers.get("Content-Type", "?")
            final = r.url
        txt = body.decode("utf-8", errors="replace")
        is_xml = "<?xml" in txt or "<akomaNtoso" in txt or "<akn:" in txt
        tag = "XML!" if is_xml else "HTML/autre"
        print("  " + (label or url) + " => [" + tag + "] CT=" + ct)
        if final != url:
            print("    redirect vers: " + final)
        if is_xml:
            print("    DEBUT: " + txt[:300])
        return is_xml, txt, final
    except urllib.error.HTTPError as e:
        print("  " + (label or url) + " => HTTP " + str(e.code))
        return None, None, None
    except Exception as e:
        print("  " + (label or url) + " => ERR " + str(e))
        return None, None, None

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v10")
print("=" * 60)
print()

# 1. Proprietes de la manifestation XML (isEmbodiedBy)
manif_xml = BASE + "/20290101/fr/xml"
sparql("SELECT ?p ?o WHERE { <" + manif_xml + "> ?p ?o } LIMIT 20",
       "1. Proprietes de la manifestation XML 20290101")

# 2. isEmbodiedBy sur toutes versions + trouver les URLs de download
sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?version ?manif ?p ?val WHERE {
  ?version jolux:isMemberOf <""" + BASE + """> ;
           jolux:isRealizedBy ?expr .
  ?expr jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
        jolux:isEmbodiedBy ?manif .
  ?manif jolux:userFormat ?fmt .
  FILTER(CONTAINS(str(?fmt), "xml") || CONTAINS(str(?manif), "xml"))
  ?manif ?p ?val .
} ORDER BY DESC(?version) LIMIT 20""", "2. Manifestations XML via isEmbodiedBy")

# 3. Tester le bon chemin /fr/xml (pas /akn/fr/xml)
print("--- 3. Telechargement avec /fr/xml ---")
print()
xml_found = None
for d in DATES:
    url = BASE + "/" + d + "/fr/xml"
    ok, txt, final = try_dl(url, d)
    if ok:
        xml_found = (url, txt)
        break
print()

# 4. Essayer aussi sur fedlex.admin.ch (le site principal)
if not xml_found:
    print("--- 4. Memes URLs sur fedlex.admin.ch ---")
    print()
    for d in DATES[:4]:
        url = "https://fedlex.admin.ch/eli/cc/1991/1184_1184_1184/" + d + "/fr/xml"
        ok, txt, final = try_dl(url, d + " (fedlex.admin.ch)")
        if ok:
            xml_found = (url, txt)
            break
    print()

# 5. Chercher l'URL reelle du fichier dans les proprietes de la manifestation
if not xml_found:
    print("--- 5. Chercher URL fichier dans proprietes manifestation ---")
    rows = sparql("""PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?manif ?p ?val WHERE {
  <""" + BASE + """/20260101/fr> jolux:isEmbodiedBy ?manif .
  ?manif ?p ?val .
  FILTER(isIRI(?val) || CONTAINS(str(?val), "http"))
} LIMIT 20""", "5a. Proprietes IRI de la manifestation XML 20260101")
    for row in rows:
        val = row.get("val", {}).get("value", "")
        if "http" in val and ("xml" in val or "file" in val or "download" in val):
            print("  Tentative: " + val)
            try_dl(val, "URL depuis RDF")

if xml_found:
    print()
    print("*** XML ACCESSIBLE: " + xml_found[0] + " ***")

print()
print("=" * 60)
print("  FIN v10")
print("=" * 60)
