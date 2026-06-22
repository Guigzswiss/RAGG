"""
Diagnostic LECTURE SEULE des circulaires AFC mal détectées.

Pour chaque PDF d'un dossier, affiche :
  - le nom de fichier
  - ce que _detect_afc_circular() retourne actuellement (d'où vient "AFC-Circ-?")
  - les premières lignes d'en-tête, pour voir pourquoi le numéro n'est pas lu

Ne modifie rien, n'indexe rien, aucun appel réseau.

Usage :
    python diag_circulars.py <dossier_des_pdf>
    python diag_circulars.py <dossier> --only-unknown   # que les AFC-Circ-?
    python diag_circulars.py <dossier> --chars 800
"""
from __future__ import annotations
import argparse
from pathlib import Path

from parse_pdf_ge import _detect_afc_circular


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", help="dossier contenant les PDF")
    ap.add_argument("--only-unknown", action="store_true",
                    help="n'afficher que les circulaires sans numéro (AFC-Circ-?)")
    ap.add_argument("--chars", type=int, default=600,
                    help="nb de caractères d'en-tête à afficher")
    args = ap.parse_args()

    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("pip install pdfplumber")

    folder = Path(args.folder)
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Aucun PDF dans {folder}")

    print(f"{len(pdfs)} PDF dans {folder}\n" + "=" * 70)

    n_ok, n_unknown, n_notcirc = 0, 0, 0
    for pdf in pdfs:
        try:
            with pdfplumber.open(pdf) as doc:
                pages = [p.extract_text() for p in doc.pages[:2] if p.extract_text()]
            full = "\n".join(pages)
        except Exception as e:
            print(f"\n[ERREUR] {pdf.name} : {e}")
            continue

        detected = _detect_afc_circular(full, pdf.name)
        if detected is None:
            status = "NON-CIRCULAIRE (parsé comme loi)"
            ref = None
            n_notcirc += 1
        else:
            ref, name = detected
            if ref == "AFC-Circ-?":
                status = "⚠ NUMÉRO NON DÉTECTÉ  → AFC-Circ-?"
                n_unknown += 1
            else:
                status = f"OK → {ref}"
                n_ok += 1

        if args.only_unknown and ref != "AFC-Circ-?":
            continue

        print(f"\n■ {pdf.name}")
        print(f"  détection : {status}")
        header = " ".join(full[: args.chars].split())
        print(f"  en-tête   : {header}")

    print("\n" + "=" * 70)
    print(f"Résumé : {n_ok} numéro OK | {n_unknown} AFC-Circ-? | "
          f"{n_notcirc} non-circulaire")


if __name__ == "__main__":
    main()
