"""
Utilitaire de diagnostic : récupère le product_id et liste les modèles disponibles.
Usage : python setup_infomaniak.py
"""
from __future__ import annotations
import sys
import urllib.request
import urllib.error
import json


def main():
    try:
        from config import INFOMANIAK_TOKEN
        print(f"Token chargé : {INFOMANIAK_TOKEN[:8]}...{INFOMANIAK_TOKEN[-4:]}")
    except Exception as e:
        print(f"Erreur lors du chargement du token : {e}")
        sys.exit(1)

    # Lister les produits AI
    print("\n[1] Récupération des produits AI Infomaniak...")
    req = urllib.request.Request(
        "https://api.infomaniak.com/2/ai",
        headers={
            "Authorization": f"Bearer {INFOMANIAK_TOKEN}",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        products = data.get("data", [])
        for p in products:
            print(f"  product_id={p.get('id')}  name={p.get('name')}  status={p.get('status')}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} : {e.reason}")

    # Lister les modèles du product_id 108639
    product_id = 108639
    print(f"\n[2] Modèles disponibles pour product_id {product_id}...")
    req2 = urllib.request.Request(
        f"https://api.infomaniak.com/2/ai/{product_id}/openai/v1/models",
        headers={
            "Authorization": f"Bearer {INFOMANIAK_TOKEN}",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req2, timeout=10) as resp:
            data2 = json.loads(resp.read())
        models = data2.get("data", [])
        for m in models:
            print(f"  id={m.get('id')}")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} : {e.reason}")

    print("\nDiagnostic terminé.")


if __name__ == "__main__":
    main()
