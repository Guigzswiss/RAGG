"""
Classifie des PDF via LLM Qwen3 (Infomaniak).
Extrait le texte du PDF, envoie au LLM, retourne le type de document.

Usage :
  python classifier.py "facture.pdf" "contrat.pdf"
  python classifier.py --dossier C:\pipeline_impression\processing

Sortie : JSON avec le type de chaque document.
Nécessite : pip install pdfplumber requests --break-system-packages
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
import pdfplumber

# --- Configuration ---
API_URL = "https://api.infomaniak.com/1/ai/108639/openai/chat/completions"
MODEL = "qwen3"
API_KEY = os.environ.get("INFOMANIAK_API_KEY", "")

TYPES_VALIDES = ["FACTURE", "BON_DE_COMMANDE", "CONTRAT", "AUTRE"]

PROMPT = """Classifie ce document dans UNE seule categorie parmi : FACTURE, BON_DE_COMMANDE, CONTRAT, AUTRE.
Reponds uniquement le mot de la categorie, rien d autre. /no_think

Contenu du document :
"""


def extraire_texte(chemin_pdf):
    """Extrait le texte des 3 premières pages d'un PDF."""
    texte = ""
    with pdfplumber.open(str(chemin_pdf)) as pdf:
        for page in pdf.pages[:3]:
            t = page.extract_text()
            if t:
                texte += t + "\n"
    return texte.strip()


def appel_llm(texte):
    """Appelle le LLM avec retry (3 tentatives, 3s entre chaque)."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT + texte[:2000]}],
        "max_tokens": 20,
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    for tentative in range(3):
        try:
            r = requests.post(API_URL, json=payload, headers=headers, timeout=60)
            if r.status_code != 200:
                print(f"HTTP {r.status_code}")
                print(f"[DEBUG] {r.text[:500]}")
                return None
            reponse = (
                r.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .upper()
            )
            for t in TYPES_VALIDES:
                if t in reponse:
                    return t
            print(f"type inattendu '{reponse}' -> AUTRE")
            return "AUTRE"
        except Exception as e:
            print(f"tentative {tentative + 1}/3 echouee ({e})")
            if tentative < 2:
                time.sleep(3)
    return None


def classifier(chemin_pdf):
    """Classifie un PDF : extraction texte + appel LLM."""
    if not API_KEY:
        print("[ERREUR] Variable INFOMANIAK_API_KEY non définie.")
        return None

    f = Path(chemin_pdf)
    if not f.exists():
        print(f"[ERREUR] Fichier introuvable : {f}")
        return None

    print(f"[EXTRACT] {f.name} -> texte...", end=" ")
    try:
        texte = extraire_texte(f)
    except Exception as e:
        print(f"ECHEC ({e})")
        return None

    if not texte:
        print("aucun texte extrait -> AUTRE")
        return "AUTRE"

    print(f"OK ({len(texte)} cars)")
    print(f"[LLM] Classification via {MODEL}...", end=" ")
    resultat = appel_llm(texte)
    if resultat:
        print(f"-> {resultat}")
    return resultat


def main():
    if len(sys.argv) < 2:
        print("Usage : python classifier.py fichier1.pdf [fichier2.pdf ...]")
        print("        python classifier.py --dossier C:\\pipeline_impression\\processing")
        print()
        print("Variable requise : INFOMANIAK_API_KEY")
        sys.exit(1)

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
        type_doc = classifier(f)
        resultats.append({
            "fichier": str(f.resolve()),
            "nom": f.name,
            "type": type_doc if type_doc else "ERREUR",
        })

    print(f"\n[RÉSULTAT JSON]")
    print(json.dumps(resultats, indent=2, ensure_ascii=False))

    if any(r["type"] == "ERREUR" for r in resultats):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
