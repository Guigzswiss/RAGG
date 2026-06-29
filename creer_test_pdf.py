"""
Crée un PDF de test dans le dossier processing.
Usage : python creer_test_pdf.py
Aucune dépendance externe nécessaire.
"""

from pathlib import Path

DOSSIER = Path(r"C:\pipeline_impression\processing")


def creer_pdf_minimal(chemin, texte="Ceci est un document PDF de test."):
    """Génère un PDF valide minimal sans librairie externe."""
    contenu_page = texte.encode("latin-1", errors="replace").decode("latin-1")

    # Structure PDF minimale
    objets = []

    # Objet 1 : Catalogue
    objets.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")

    # Objet 2 : Pages
    objets.append("2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj")

    # Objet 3 : Page
    objets.append(
        "3 0 obj\n"
        "<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 595 842] "
        "/Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>\n"
        "endobj"
    )

    # Objet 4 : Contenu (texte sur la page)
    stream = f"BT /F1 16 Tf 50 750 Td ({contenu_page}) Tj ET"
    objets.append(f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj")

    # Objet 5 : Police
    objets.append("5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj")

    # Assembler le PDF
    pdf = "%PDF-1.4\n"
    offsets = []
    for obj in objets:
        offsets.append(len(pdf))
        pdf += obj + "\n"

    xref_pos = len(pdf)
    pdf += "xref\n"
    pdf += f"0 {len(objets) + 1}\n"
    pdf += "0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"

    pdf += "trailer\n"
    pdf += f"<< /Size {len(objets) + 1} /Root 1 0 R >>\n"
    pdf += "startxref\n"
    pdf += f"{xref_pos}\n"
    pdf += "%%EOF\n"

    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(pdf, encoding="latin-1")
    print(f"[OK] PDF créé : {chemin}")
    print(f"     Taille : {chemin.stat().st_size} octets")


def main():
    DOSSIER.mkdir(parents=True, exist_ok=True)

    # Créer un PDF de test simple
    creer_pdf_minimal(
        DOSSIER / "test.pdf",
        "Ceci est un document PDF de test pour le pipeline d'impression."
    )

    # Créer quelques PDF supplémentaires pour tester l'ordre d'impression
    creer_pdf_minimal(DOSSIER / "facture_001.pdf", "FACTURE #001 - Client ABC - CHF 1500.00")
    creer_pdf_minimal(DOSSIER / "bon_commande_042.pdf", "BON DE COMMANDE #042 - Fournitures bureau")
    creer_pdf_minimal(DOSSIER / "contrat_location.pdf", "CONTRAT DE LOCATION - Rue du Rhone 12, Geneve")

    print(f"\n[RÉSUMÉ] 4 PDF de test créés dans {DOSSIER}")
    print("\nPour tester l'impression :")
    print(f'  python imprimer.py "{DOSSIER / "test.pdf"}"')
    print("\nPour tester plusieurs fichiers dans l'ordre :")
    print(f'  python imprimer.py "{DOSSIER / "facture_001.pdf"}" "{DOSSIER / "bon_commande_042.pdf"}" "{DOSSIER / "contrat_location.pdf"}"')


if __name__ == "__main__":
    main()
