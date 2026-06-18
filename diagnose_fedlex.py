# -*- coding: utf-8 -*-
"""
Diagnostic Fedlex v4 - cible fedlex.data.admin.ch (backend Casemates).
Lance : python diagnose_fedlex.py > diag_output.txt 2>&1
Copie diag_output.txt dans le chat.
"""
import urllib.request, urllib.parse, urllib.error, json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "gsass-rag/1.0"
LIFD = "cc/1991/1184_1184_1184"

def get(url, headers, method="GET", data=None):
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(1000)
            ct = r.headers.get("Content-Type","?")
            final_url = r.url
        txt = body.decode("utf-8", errors="replace")
        is_html = txt.strip().startswith("<!") or "<html" in txt[:100]
        status = "HTML" if is_html else "CONTENU"
        print("  " + method + " " + url)
        print("  => HTTP 200 [" + status + "] CT=" + ct)
        if not is_html:
            print("  DEBUT: " + txt[:400])
        return txt, not is_html
    except urllib.error.HTTPError as e:
        print("  " + method + " " + url + " => HTTP " + str(e.code))
        return None, False
    except Exception as e:
        print("  " + method + " " + url + " => ERR " + str(e))
        return None, False

print("=" * 60)
print("  DIAGNOSTIC FEDLEX v4")
print("=" * 60)
print()

# ── 1. SPARQL sur fedlex.data.admin.ch ───────────────────────────────────────
print("--- 1. SPARQL sur fedlex.data.admin.ch ---")
print()
query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"

sparql_urls = [
    "https://fedlex.data.admin.ch/sparql",
    "https://fedlex.data.admin.ch/sparqlendpoint",
    "https://fedlex.data.admin.ch/query",
    "https://fedlex.data.admin.ch/api/sparql",
    "https://fedlex.data.admin.ch/repositories/FEDLEX",
]
for url in sparql_urls:
    data = urllib.parse.urlencode({"query": query}).encode()
    txt, ok = get(url, {"Accept":"application/sparql-results+json","Content-Type":"application/x-www-form-urlencoded","User-Agent":UA}, "POST", data)
    if ok:
        print("  *** SPARQL FONCTIONNE ICI ***")
    print()

# ── 2. Fichiers XML sur fedlex.data.admin.ch ──────────────────────────────────
print("--- 2. Fichiers XML sur fedlex.data.admin.ch ---")
print()
file_urls = [
    "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/" + LIFD + "/fr/akn/fr/xml",
    "https://fedlex.data.admin.ch/eli/" + LIFD + "/fr/akn/fr/xml",
    "https://fedlex.data.admin.ch/eli/" + LIFD + "/fr",
    "https://fedlex.data.admin.ch/filestore/eli/" + LIFD + "/fr/akn/fr/xml",
]
for url in file_urls:
    txt, ok = get(url, {"Accept":"application/xml, */*","User-Agent":UA})
    if ok:
        print("  *** XML TROUVE ***")
        print("  DEBUT XML: " + txt[:500])
    print()

# ── 3. HEAD requests pour voir les vrais redirects ────────────────────────────
print("--- 3. HEAD requests (pour voir les redirects) ---")
print()
head_urls = [
    "https://www.fedlex.admin.ch/filestore/fedlex.data.admin.ch/eli/" + LIFD + "/fr/akn/fr/xml",
    "https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/" + LIFD + "/fr/akn/fr/xml",
]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirect)
for url in head_urls:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":UA})
        with opener.open(req, timeout=10) as r:
            loc = r.headers.get("Location","(pas de redirect)")
            ct  = r.headers.get("Content-Type","?")
            print("  HEAD " + url)
            print("  => " + str(r.status) + " CT=" + ct + " Location=" + loc)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location","") if e.headers else ""
        print("  HEAD " + url + " => HTTP " + str(e.code) + " Location=" + loc)
    except Exception as e:
        print("  HEAD " + url + " => ERR " + str(e))
    print()

# ── 4. Verifier si l'API REST Fedlex existe ───────────────────────────────────
print("--- 4. API REST Fedlex ---")
print()
api_urls = [
    "https://fedlex.data.admin.ch/mam/api/",
    "https://fedlex.data.admin.ch/mam/api/v1/",
    "https://fedlex.data.admin.ch/api/",
    "https://fedlex.data.admin.ch/cgi-bin/broker.pl?userhome=home&action=home&language=fr",
]
for url in api_urls:
    get(url, {"Accept":"application/json, text/html","User-Agent":UA})
    print()

print("=" * 60)
print("  FIN DIAGNOSTIC v4")
print("=" * 60)
