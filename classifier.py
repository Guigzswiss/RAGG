"""
Classifie des PDF selon les codes fiscaux genevois et les trie
dans l'ordre de la declaration d'impot.

Usage :
  python classifier.py "facture.pdf" "contrat.pdf"
  python classifier.py --dossier C:\pipeline_impression\processing

Sortie : JSON avec le code fiscal et la priorite de chaque document.
Necessite : pip install pdfplumber requests --break-system-packages
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

SCRIPT_DIR = Path(__file__).parent.resolve()
ORDRE_TRI_PATH = SCRIPT_DIR / "ordre_tri.json"

with open(ORDRE_TRI_PATH, encoding="utf-8") as f:
    ORDRE_TRI = json.load(f)

CODES_VALIDES = [item["code"] for item in ORDRE_TRI]
CODE_TO_PRIORITE = {item["code"]: item["priorite"] for item in ORDRE_TRI}
CODE_TO_DESC = {item["code"]: item["description"] for item in ORDRE_TRI}

CODES_LISTE = "\n".join(
    f"- {item['code']} : {item['description']}" for item in ORDRE_TRI
)

PROMPT = f"""Tu es un assistant de fiduciaire a Geneve. Analyse le contenu de ce document et identifie a quel code fiscal de la declaration d'impot genevoise il correspond.

Voici les codes possibles :
{CODES_LISTE}

Reponds UNIQUEMENT avec le code (par exemple : 11.10 ou 52.11 ou COMPTES_BANCAIRES). Rien d'autre. /no_think

Contenu du document :
"""


def extraire_texte(chemin_pdf):
    """Extrait le texte des 3 premieres pages d'un PDF."""
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
        "messages": [{"role": "user", "content": PROMPT + texte[:3000]}],
        "max_tokens": 30,
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
            )
            # Chercher un code valide dans la reponse
            for code in CODES_VALIDES:
                if code in reponse:
                    return code
            print(f"code inconnu '{reponse}'")
            return "AUTRE"
        except Exception as e:
            print(f"tentative {tentative + 1}/3 echouee ({e})")
            if tentative < 2:
                time.sleep(3)
    return None


def classifier(chemin_pdf):
    """Classifie un PDF : extraction texte + appel LLM."""
    if not API_KEY:
        print("[ERREUR] Variable INFOMANIAK_API_KEY non definie.")
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
    code = appel_llm(texte)
    if code and code != "AUTRE":
        desc = CODE_TO_DESC.get(code, "")
        print(f"-> {code} ({desc})")
    elif code == "AUTRE":
        print("-> AUTRE (non reconnu)")
    return code


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
        code = classifier(f)
        priorite = CODE_TO_PRIORITE.get(code, 999) if code else 999
        resultats.append({
            "fichier": str(f.resolve()),
            "nom": f.name,
            "code": code if code else "AUTRE",
            "description": CODE_TO_DESC.get(code, "Non classe"),
            "priorite": priorite,
        })

    # Trier par priorite
    resultats.sort(key=lambda x: x["priorite"])

    print(f"\n[RESULTAT JSON — trie par ordre de declaration]")
    print(json.dumps(resultats, indent=2, ensure_ascii=False))

    if any(r["code"] == "AUTRE" or r["priorite"] == 999 for r in resultats):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
