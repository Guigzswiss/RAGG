"""
Serveur Flask unifie pour le pipeline fiduciaire.
Combine le classement client (emails) et l'impression fiscale.

Endpoints :
  POST /creer_dossier         - Cree un dossier client
  POST /sauvegarder_fichier   - Sauvegarde un fichier (base64) dans un dossier
  POST /pipeline_complet      - Classement client + classification fiscale + impression

Usage : python serveur.py [--port 5000] [--dossier-impression C:\pipeline_impression]
Necessite : pip install flask pdfplumber requests --break-system-packages
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

SCRIPT_DIR = Path(__file__).parent.resolve()
DOSSIER_IMPRESSION = Path(os.environ.get(
    "DOSSIER_IMPRESSION", r"C:\pipeline_impression"
))


@app.route("/creer_dossier", methods=["POST"])
def creer_dossier():
    """Cree un dossier sur le disque."""
    data = request.get_json(force=True)
    chemin = data.get("chemin")
    if not chemin:
        return jsonify({"erreur": "chemin manquant"}), 400

    try:
        Path(chemin).mkdir(parents=True, exist_ok=True)
        return jsonify({"statut": "ok", "chemin": chemin})
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


@app.route("/sauvegarder_fichier", methods=["POST"])
def sauvegarder_fichier():
    """Sauvegarde un fichier encode en base64 dans un dossier."""
    data = request.get_json(force=True)
    chemin_dossier = data.get("chemin_dossier")
    nom_fichier = data.get("nom_fichier")
    contenu_base64 = data.get("contenu_base64")

    if not all([chemin_dossier, nom_fichier, contenu_base64]):
        return jsonify({"erreur": "chemin_dossier, nom_fichier et contenu_base64 requis"}), 400

    try:
        dossier = Path(chemin_dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        fichier = dossier / nom_fichier
        fichier.write_bytes(base64.b64decode(contenu_base64))
        return jsonify({
            "statut": "ok",
            "fichier": str(fichier),
            "taille": fichier.stat().st_size,
        })
    except Exception as e:
        return jsonify({"erreur": str(e)}), 500


@app.route("/pipeline_complet", methods=["POST"])
def pipeline_complet():
    """
    Pipeline complet : classement client + classification fiscale + impression.

    Body JSON :
    {
      "client": "Nom du client",
      "type_document": "TVA",
      "annee": "2026",
      "pieces_jointes": [
        {"nom": "facture.pdf", "contenu_base64": "..."}
      ],
      "imprimer": true   (optionnel, defaut true)
    }

    Etapes :
    1. Sauvegarde les pieces jointes dans H:/Clients/{client}/{annee}/{type_document}
    2. Copie les PDF dans pipeline_impression/processing
    3. Lance classifier.py pour trier par code fiscal
    4. Lance imprimer.py pour imprimer dans l'ordre
    5. Deplace les PDF traites vers done/
    """
    data = request.get_json(force=True)

    client = data.get("client")
    type_document = data.get("type_document")
    annee = data.get("annee")
    pieces_jointes = data.get("pieces_jointes", [])
    faire_impression = data.get("imprimer", True)

    if not all([client, type_document, annee]):
        return jsonify({"erreur": "client, type_document et annee requis"}), 400

    if not pieces_jointes:
        return jsonify({"erreur": "pieces_jointes vide"}), 400

    resultats = {
        "client": client,
        "classement": [],
        "classification_fiscale": [],
        "impression": [],
        "erreurs": [],
    }

    # --- Etape 1 : Sauvegarder sous le client ---
    chemin_client = Path(f"H:/Clients/{client}/{annee}/{type_document}")
    try:
        chemin_client.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        resultats["erreurs"].append(f"Creation dossier client: {e}")

    fichiers_sauves = []
    for pj in pieces_jointes:
        nom = pj.get("nom", "sans_nom.pdf")
        contenu_b64 = pj.get("contenu_base64", "")
        if not contenu_b64:
            resultats["erreurs"].append(f"Pas de contenu pour {nom}")
            continue

        try:
            dest = chemin_client / nom
            if dest.exists():
                dest = chemin_client / f"{dest.stem}_{int(time.time())}{dest.suffix}"
            dest.write_bytes(base64.b64decode(contenu_b64))
            fichiers_sauves.append(str(dest))
            resultats["classement"].append({
                "fichier": str(dest),
                "nom": nom,
                "statut": "ok",
            })
        except Exception as e:
            resultats["erreurs"].append(f"Sauvegarde {nom}: {e}")

    # --- Etape 2 : Copier les PDF dans processing pour impression ---
    if not faire_impression:
        return jsonify(resultats)

    processing = DOSSIER_IMPRESSION / "processing"
    done = DOSSIER_IMPRESSION / "done"
    processing.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)

    pdfs_processing = []
    for chemin_fichier in fichiers_sauves:
        p = Path(chemin_fichier)
        if p.suffix.lower() != ".pdf":
            continue
        try:
            dest = processing / p.name
            if dest.exists():
                dest = processing / f"{p.stem}_{int(time.time())}{p.suffix}"
            shutil.copy2(str(p), str(dest))
            pdfs_processing.append(dest)
        except Exception as e:
            resultats["erreurs"].append(f"Copie vers processing {p.name}: {e}")

    if not pdfs_processing:
        resultats["erreurs"].append("Aucun PDF a imprimer")
        return jsonify(resultats)

    # --- Etape 3 : Classifier par code fiscal ---
    python_exe = sys.executable
    classifier_py = SCRIPT_DIR / "classifier.py"

    try:
        result = subprocess.run(
            [python_exe, str(classifier_py), "--dossier", str(processing)],
            capture_output=True, text=True, timeout=300,
            env={**os.environ},
        )
        lignes = result.stdout.split("\n")
        marker = next(i for i, l in enumerate(lignes) if "RESULTAT JSON" in l)
        json_str = "\n".join(lignes[marker + 1:])
        documents = json.loads(json_str)
        chemins_ordonnes = [d["fichier"] for d in documents]
        resultats["classification_fiscale"] = documents
    except Exception as e:
        resultats["erreurs"].append(f"Classification fiscale: {e}")
        chemins_ordonnes = [str(p) for p in sorted(pdfs_processing)]

    # --- Etape 4 : Imprimer dans l'ordre ---
    imprimer_py = SCRIPT_DIR / "imprimer.py"

    try:
        cmd = [python_exe, str(imprimer_py)] + chemins_ordonnes
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        resultats["impression"].append({
            "sortie": result.stdout,
            "code_retour": result.returncode,
        })
    except Exception as e:
        resultats["erreurs"].append(f"Impression: {e}")

    # --- Etape 5 : Deplacer vers done ---
    for pdf in pdfs_processing:
        try:
            dest_done = done / pdf.name
            if dest_done.exists():
                dest_done = done / f"{pdf.stem}_{int(time.time())}{pdf.suffix}"
            shutil.move(str(pdf), str(dest_done))
        except Exception as e:
            resultats["erreurs"].append(f"Deplacement done {pdf.name}: {e}")

    return jsonify(resultats)


@app.route("/statut", methods=["GET"])
def statut():
    """Verifie que le serveur est en ligne."""
    return jsonify({
        "statut": "ok",
        "scripts": str(SCRIPT_DIR),
        "dossier_impression": str(DOSSIER_IMPRESSION),
    })


def main():
    port = 5000
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--dossier-impression" and i + 1 < len(args):
            global DOSSIER_IMPRESSION
            DOSSIER_IMPRESSION = Path(args[i + 1])
            i += 2
        else:
            i += 1

    print(f"[SERVEUR] Scripts : {SCRIPT_DIR}")
    print(f"[SERVEUR] Dossier impression : {DOSSIER_IMPRESSION}")
    print(f"[SERVEUR] Demarrage sur http://127.0.0.1:{port}")
    print(f"[SERVEUR] Endpoints :")
    print(f"  POST /creer_dossier        - Cree un dossier")
    print(f"  POST /sauvegarder_fichier  - Sauvegarde un fichier (base64)")
    print(f"  POST /pipeline_complet     - Classement + impression")
    print(f"  GET  /statut               - Verification")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
