"""
Script d'impression silencieuse via SumatraPDF.
Usage : python imprimer.py "doc1.pdf" "doc2.pdf" ...
Code de sortie : 0 = tous imprimés, 1 = au moins un échec.
"""

import subprocess
import sys
from pathlib import Path


def trouver_sumatra():
    """Cherche SumatraPDF dans les emplacements d'installation courants."""
    candidats = [
        Path(r"C:\Program Files\SumatraPDF\SumatraPDF.exe"),
        Path(r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe"),
        Path.home() / "AppData" / "Local" / "SumatraPDF" / "SumatraPDF.exe",
        Path(r"C:\Users") / Path.home().name / "scoop" / "apps" / "sumatrapdf" / "current" / "SumatraPDF.exe",
    ]
    for chemin in candidats:
        if chemin.exists():
            return str(chemin)

    # Tenter via PATH (winget installe parfois dans le PATH)
    try:
        result = subprocess.run(
            ["where", "SumatraPDF.exe"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def imprimer(chemin_pdf, imprimante=None, sumatra_exe=None):
    """Imprime un PDF via SumatraPDF. Retourne True si succès, False sinon."""
    pdf = Path(chemin_pdf).resolve()

    if not pdf.exists():
        print(f"[ERREUR] Fichier introuvable : {pdf}")
        # Aide au diagnostic : lister le contenu du dossier parent
        parent = pdf.parent
        if parent.exists():
            fichiers = list(parent.iterdir())
            if fichiers:
                print(f"         Fichiers présents dans {parent} :")
                for f in fichiers:
                    print(f"           - {f.name}")
            else:
                print(f"         Le dossier {parent} est vide.")
        else:
            print(f"         Le dossier {parent} n'existe pas non plus.")
        return False

    if not pdf.suffix.lower() == ".pdf":
        print(f"[ERREUR] Ce n'est pas un PDF : {pdf}")
        return False

    if sumatra_exe is None:
        sumatra_exe = trouver_sumatra()
    if sumatra_exe is None:
        print("[ERREUR] SumatraPDF introuvable. Installe-le avec : winget install SumatraPDF.SumatraPDF")
        return False

    cmd = [sumatra_exe, "-print-to-default", "-silent", str(pdf)]
    if imprimante:
        cmd = [sumatra_exe, "-print-to", imprimante, "-silent", str(pdf)]

    print(f"[IMPRESSION] {pdf.name} ...", end=" ")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print("OK")
            return True
        else:
            print(f"ECHEC (code {result.returncode})")
            if result.stderr:
                print(f"             {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print("ECHEC (timeout 60s)")
        return False
    except FileNotFoundError:
        print(f"ECHEC (exécutable introuvable : {sumatra_exe})")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage : python imprimer.py fichier1.pdf [fichier2.pdf ...]")
        print("Options :")
        print("  --imprimante NOM   Imprimante cible (défaut : imprimante par défaut)")
        sys.exit(1)

    # Parser les arguments
    args = sys.argv[1:]
    imprimante = None
    fichiers = []

    i = 0
    while i < len(args):
        if args[i] == "--imprimante" and i + 1 < len(args):
            imprimante = args[i + 1]
            i += 2
        else:
            fichiers.append(args[i])
            i += 1

    if not fichiers:
        print("[ERREUR] Aucun fichier PDF spécifié.")
        sys.exit(1)

    # Trouver SumatraPDF une seule fois
    sumatra_exe = trouver_sumatra()

    succes = 0
    echecs = 0

    for f in fichiers:
        if imprimer(f, imprimante=imprimante, sumatra_exe=sumatra_exe):
            succes += 1
        else:
            echecs += 1

    print(f"\n[RÉSUMÉ] {succes} imprimé(s), {echecs} échec(s)")
    sys.exit(0 if echecs == 0 else 1)


if __name__ == "__main__":
    main()
