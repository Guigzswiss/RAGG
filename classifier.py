"""
Classifie des PDF via OCR Gemma 4 (Infomaniak).
Convertit le PDF en image, envoie à l'API, retourne le type de document.

Usage :
  python classifier.py "facture.pdf" "contrat.pdf"
  python classifier.py --dossier C:\pipeline_impression\processing

Sortie : JSON avec le type de chaque document.
Nécessite : pip install pdf2image requests --break-system-packages
Nécessite aussi : poppler (pour pdf2image) — voir README.
"""

import base64
import json
import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from pdf2image import convert_from_path

# --- Configuration ---
API_URL = "https://api.infomaniak.com/1/ai/108639/openai/chat/completions"
MODEL = "google/gemma-4-31B-it"

# La clé API est lue depuis la variable d'environnement INFOMANIAK_API_KEY
# Pour la définir : $env:INFOMANIAK_API_KEY = "ta_cle_ici" (PowerShell)
API_KEY = os.environ.get("INFOMANIAK_API_KEY", "")

TYPES_VALIDES = ["FACTURE", "BON_DE_COMMANDE", "CONTRAT", "AUTRE"]

PROMPT_CLASSIFICATION = """Analyse ce document et classifie-le dans exactement UNE de ces catégories :
- FACTURE : facture, note de frais, relevé, décompte
- BON_DE_COMMANDE : bon de commande, commande, order
- CONTRAT : contrat, bail, convention, accord, mandat
- AUTRE : tout document qui ne rentre pas dans les catégories ci-dessus

Réponds UNIQUEMENT avec le nom de la catégorie, rien d'autre. Par exemple : FACTURE"""


def pdf_vers_image_base64(chemin_pdf, dpi=200):
    """Convertit la première page d'un PDF en image base64 (JPEG)."""
    chemin = Path(chemin_pdf).resolve()
    if not chemin.exists():
        raise FileNotFoundError(f"PDF introuvable : {chemin}")

    images = convert_from_path(str(chemin), dpi=dpi, first_page=1, last_page=1)
    if not images:
        raise ValueError(f"Impossible de convertir {chemin} en image")

    buffer = BytesIO()
    images[0].save(buffer, format="JPEG", quality=85)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return b64


def classifier_document(chemin_pdf):
    """Envoie l'image du PDF à Gemma 4 et retourne le type de document."""
    if not API_KEY:
        print("[ERREUR] Variable INFOMANIAK_API_KEY non définie.")
        print("         Définis-la avec : $env:INFOMANIAK_API_KEY = \"ta_cle\"")
        return None

    print(f"[OCR] Conversion de {Path(chemin_pdf).name} en image...", end=" ")
    try:
        image_b64 = pdf_vers_image_base64(chemin_pdf)
    except Exception as e:
        print(f"ECHEC ({e})")
        return None
    print("OK")

    print(f"[OCR] Envoi à Gemma 4 pour classification...", end=" ")
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": PROMPT_CLASSIFICATION
                    }
                ]
            }
        ],
        "max_tokens": 20,
        "temperature": 0
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"ECHEC (HTTP {resp.status_code})")
        print(f"         Réponse : {resp.text[:200]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ECHEC ({e})")
        return None

    data = resp.json()
    reponse = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().upper()
    print(f"OK → {reponse}")

    # Valider que la réponse est un type connu
    if reponse not in TYPES_VALIDES:
        print(f"[ATTENTION] Type inattendu '{reponse}', classé comme AUTRE")
        reponse = "AUTRE"

    return reponse


def main():
    if len(sys.argv) < 2:
        print("Usage : python classifier.py fichier1.pdf [fichier2.pdf ...]")
        print("        python classifier.py --dossier C:\\pipeline_impression\\processing")
        print()
        print("Variable requise : INFOMANIAK_API_KEY")
        sys.exit(1)

    # Parser les arguments
    args = sys.argv[1:]
    fichiers = []

    if args[0] == "--dossier" and len(args) >= 2:
        dossier = Path(args[1])
        if not dossier.exists():
            print(f"[ERREUR] Dossier introuvable : {dossier}")
            sys.exit(1)
        fichiers = sorted(dossier.glob("*.pdf"))
        if not fichiers:
            print(f"[ERREUR] Aucun PDF dans {dossier}")
            sys.exit(1)
    else:
        fichiers = [Path(a) for a in args]

    resultats = []

    for f in fichiers:
        type_doc = classifier_document(f)
        resultats.append({
            "fichier": str(f.resolve()),
            "nom": f.name,
            "type": type_doc if type_doc else "ERREUR"
        })

    print("\n[RÉSULTAT JSON]")
    print(json.dumps(resultats, indent=2, ensure_ascii=False))

    # Code de sortie : 1 si au moins une erreur
    if any(r["type"] == "ERREUR" for r in resultats):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
