"""
Surveille le dossier inbox et déplace les nouveaux PDF vers processing.
Usage : python watcher.py [--dossier C:\\pipeline_impression]
Nécessite : pip install watchdog --break-system-packages
"""

import shutil
import sys
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


DOSSIER_BASE = Path(r"C:\pipeline_impression")


class PDFHandler(FileSystemEventHandler):
    """Réagit quand un nouveau fichier apparaît dans inbox."""

    def __init__(self, dossier_processing, dossier_done):
        self.dossier_processing = dossier_processing
        self.dossier_done = dossier_done

    def on_created(self, event):
        if event.is_directory:
            return
        chemin = Path(event.src_path)
        if chemin.suffix.lower() != ".pdf":
            return

        # Attendre que le fichier soit complètement écrit
        taille_avant = -1
        for _ in range(10):
            try:
                taille = chemin.stat().st_size
                if taille == taille_avant and taille > 0:
                    break
                taille_avant = taille
                time.sleep(0.5)
            except OSError:
                return

        dest = self.dossier_processing / chemin.name
        print(f"[WATCHER] Nouveau PDF détecté : {chemin.name}")
        try:
            shutil.move(str(chemin), str(dest))
            print(f"[WATCHER] Déplacé vers processing : {dest}")
        except Exception as e:
            print(f"[ERREUR] Impossible de déplacer {chemin.name} : {e}")
            return

        traiter_pdf(dest, self.dossier_done)


def traiter_pdf(chemin_pdf, dossier_done):
    """Squelette : sera complété avec OCR + classification + impression."""
    print(f"[TRAITEMENT] {chemin_pdf.name} — (squelette, pas encore implémenté)")
    # TODO étape 3 : appeler classifier.py (OCR Gemma 4)
    # TODO étape 5 : appeler imprimer.py


def main():
    dossier_base = DOSSIER_BASE

    # Argument optionnel : --dossier
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--dossier" and i + 1 < len(args):
            dossier_base = Path(args[i + 1])
            i += 2
        else:
            i += 1

    inbox = dossier_base / "inbox"
    processing = dossier_base / "processing"
    done = dossier_base / "done"

    # Créer les dossiers s'ils n'existent pas
    for d in [inbox, processing, done]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Dossier prêt : {d}")

    handler = PDFHandler(processing, done)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()

    print(f"\n[WATCHER] Surveillance de {inbox} — Ctrl+C pour arrêter.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("[WATCHER] Arrêté.")


if __name__ == "__main__":
    main()
