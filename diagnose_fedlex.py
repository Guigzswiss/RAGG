# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v3 - teste plusieurs patterns d'URL et de SPARQL.
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
Copie diag_output.txt dans le chat.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def try_url(label, url, headers):
    print("  " + label)
    print("  URL: " + url)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(800)
            ct = resp.headers.get("Content-Type", "?")
        decoded = body.decode("utf-8", errors="replace")
        print("  HTTP 200 - Content-Type: " + ct)
        print("  Debut: " + decoded[:300])
        return decoded, True
    except urllib.error.HTTPError as e:
        print("  HTTP " + str(e.code) + " " + str(e.reason))
        return None, False
    except Exception as e:
        print("  ERREUR: " + str(e))
        return None, False
    finally:
        print()

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v3")
print("=" * 60)

LIFD_ELI_ID = "cc/1991/1184_1184_1184"
UA = "gsass-rag/1.0 (recherche juridique; contact: guillaume.droz06@gmail.com)"

# ── 1. SPARQL avec differents endpoints ───────────────────────────────────────
print()
print("--- 1. SPARQL ---")

query = """SELECT ?expr ?title WHERE {
  ?work <http://data.legilux.public.lu/resource/ontology/jolux#classifiedByTaxonomyEntry>
        <https://fedlex.admin.ch/vocabulary/legal-taxonomy/642.11> ;
        <http://data.legilux.public.lu/resource/ontology/jolux#hasExpression> ?expr .
  ?expr <http://data.legilux.public.lu/resource/ontology/jolux#language>
        <http://publications.europa.eu/resource/authority/language/FRA> ;
        <http://schema.org/name> ?title .
} LIMIT 3"""

sparql_endpoints = [
    "https://fedlex.admin.ch/sparqlendpoint",
    "https://www.fedlex.admin.ch/sparqlendpoint",
    "https://fedlex.admin.ch/api/sparql",
]

for ep in sparql_endpoints:
    post_data = urllib.parse.urlencode({"query": query}).encode()
    print("  Endpoint: " + ep)
    try:
        req = urllib.request.Request(ep, data=post_data, headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(400)
            ct = resp.headers.get("Content-Type", "?")
        decoded = body.decode("utf-8", errors="replace")
        print("  HTTP 200 - CT: " + ct)
        print("  Debut: " + decoded[:200])
        if "{" in decoded and "results" in decoded:
            print("  => JSON SPARQL detecte!")
        else:
            print("  => HTML (SPA) - pas un SPARQL endpoint")
    except urllib.error.HTTPError as e:
        print("  HTTP " + str(e.code))
    except Exception as e:
        print("  ERREUR: " + str(e))
    print()

# ── 2. URLs XML directes ──────────────────────────────────────────────────────
print("--- 2. URLs XML directes ---")
print()

xml_candidates = [
    ("www + filestore + /akn/fr/xml",
     "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/" + LIFD_ELI_ID + "/fr/akn/fr/xml",
     {"Accept": "application/xml", "User-Agent": UA}),

    ("fedlex.admin.ch + filestore + /akn/fr/xml",
     "https://fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/" + LIFD_ELI_ID + "/fr/akn/fr/xml",
     {"Accept": "application/xml", "User-Agent": UA}),

    ("ELI direct + Accept XML (content negotiation)",
     "https://www.fedlex.admin.ch/eli/" + LIFD_ELI_ID + "/fr",
     {"Accept": "application/akn+xml, application/xml;q=0.9", "User-Agent": UA}),

    ("ELI direct + /akn/fr/xml",
     "https://www.fedlex.admin.ch/eli/" + LIFD_ELI_ID + "/fr/akn/fr/xml",
     {"Accept": "application/xml", "User-Agent": UA}),

    ("data.admin.ch filestore direct",
     "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/" + LIFD_ELI_ID + "/fr/akn/fr/xml",
     {"Accept": "application/xml", "User-Agent": UA}),

    ("download.admin.ch",
     "https://www.admin.ch/opc/fr/classified-compilation/19900329/index.html",
     {"Accept": "text/html", "User-Agent": UA}),
]

working = []
for label, url, hdrs in xml_candidates:
    body, ok = try_url(label, url, hdrs)
    if ok and body and "<" in body and "html" not in body[:50].lower():
        working.append((label, url, body))
        print("  *** POTENTIELLEMENT DU XML ***")
        print()

# ── 3. Si XML trouve, analyser sa structure ───────────────────────────────────
if working:
    print("--- 3. ANALYSE XML ---")
    for label, url, preview in working:
        print("Source: " + label)
        # Telecharger complet
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/xml", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                full = resp.read().decode("utf-8", errors="replace")
            print("Taille: " + str(len(full)) + " chars")
            lines = full.splitlines()
            print("Lignes: " + str(len(lines)))
            print()
            print("--- 50 premieres lignes ---")
            for l in lines[:50]:
                print(l)
            print("--- fin ---")
            print()

            import xml.etree.ElementTree as ET
            root = ET.fromstring(full)
            ns_found = set()
            article_count = 0
            for elem in root.iter():
                if elem.tag.startswith("{"):
                    ns_found.add(elem.tag.split("}")[0][1:])
                local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if local == "article":
                    article_count += 1
                    if article_count <= 2:
                        print("Article #" + str(article_count))
                        print("  tag : " + elem.tag)
                        print("  eId : " + str(elem.get("eId", "ABSENT")))
                        print("  texte: " + " ".join(elem.itertext())[:250])
                        print()
            print("Namespaces: " + str(sorted(ns_found)))
            print("Total articles: " + str(article_count))
        except Exception as e:
            print("Erreur analyse: " + str(e))
else:
    print("--- Aucun XML trouve. Diagnostic supplementaire ---")
    print()
    print("Tentative sur opengov.ch (ancienne API):")
    try_url("opengov.ch API",
            "https://api.opengov.ch/api/v1/laws/fr/642.11",
            {"Accept": "application/json", "User-Agent": UA})

    print("Tentative download direct swisstopo:")
    try_url("swisstopo fedlex",
            "https://swisstopo.admin.ch",
            {"Accept": "text/html", "User-Agent": UA})

print()
print("=" * 60)
print("  FIN - copie diag_output.txt dans le chat")
print("=" * 60)
