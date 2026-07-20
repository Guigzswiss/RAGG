"""
Surveille le dossier inbox, classifie et imprime les PDF automatiquement.
Usage : python watcher.py [--dossier C:\\pipeline_impression]

Flux : inbox -> processing -> classifier -> imprimer -> done
Le watcher fonctionne en autonome (sans serveur Flask).
Pour le flux email, utiliser serveur.py + n8n.

Necessite : pip install watchdog pdfplumber requests --break-system-packages
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


DOSSIER_BASE = Path(r"C:\pipeline_impression")
SCRIPT_DIR = Path(__file__).parent.resolve()


class PDFHandler(FileSystemEventHandler):
    """Reagit quand un nouveau fichier apparait dans inbox."""

    def __init__(self, dossier_base, python_exe):
        self.inbox = dossier_base / "inbox"
        self.processing = dossier_base / "processing"
        self.done = dossier_base / "done"
        self.python_exe = python_exe
        self.attente = {}

    def on_created(self, event):
        if event.is_directory:
            return
        chemin = Path(event.src_path)
        if chemin.suffix.lower() != ".pdf":
            return

        # Attendre que le fichier soit completement ecrit
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

        dest = self.processing / chemin.name
        print(f"\n[WATCHER] Nouveau PDF detecte : {chemin.name}")
        try:
            shutil.move(str(chemin), str(dest))
            print(f"[WATCHER] Deplace vers processing : {dest.name}")
        except Exception as e:
            print(f"[ERREUR] Impossible de deplacer {chemin.name} : {e}")
            return

        # Attendre un peu pour regrouper les fichiers
        # (si plusieurs PDF arrivent en meme temps)
        self.attente[dest.name] = time.time()
        time.sleep(3)

        # Verifier si de nouveaux fichiers sont arrives entre-temps
        if time.time() - max(self.attente.values()) < 2:
            time.sleep(2)

        # Lancer le pipeline sur tous les PDF dans processing
        self.lancer_pipeline()
        self.attente.clear()

    def lancer_pipeline(self):
        """Lance classifier.py puis imprimer.py sur processing/."""
        pdfs = sorted(self.processing.glob("*.pdf"))
        if not pdfs:
            print("[WATCHER] Aucun PDF dans processing, rien a faire.")
            return

        print(f"\n{'='*50}")
        print(f"[PIPELINE] {len(pdfs)} PDF a traiter")
        print(f"{'='*50}")

        # Etape 1 : Classifier et trier
        classifier_py = SCRIPT_DIR / "classifier.py"
        print(f"\n[ETAPE 1/2] Classification et tri...")
        try:
            result = subprocess.run(
                [str(self.python_exe), str(classifier_py), "--dossier", str(self.processing)],
                capture_output=True, text=True, timeout=300
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
        except subprocess.TimeoutExpired:
            print("[ERREUR] Timeout du classifier (5 min)")
            return
        except Exception as e:
            print(f"[ERREUR] Classifier : {e}")
            return

        # Parser le JSON de sortie pour obtenir l'ordre
        try:
            lignes = result.stdout.split("\n")
            marker = next(i for i, l in enumerate(lignes) if "RESULTAT JSON" in l)
            json_str = "\n".join(lignes[marker + 1:])
            documents = json.loads(json_str)
            chemins_ordonnes = [d["fichier"] for d in documents]
        except Exception as e:
            print(f"[ERREUR] Impossible de parser le resultat du classifier : {e}")
            print("[FALLBACK] Impression dans l'ordre alphabetique")
            chemins_ordonnes = [str(p) for p in pdfs]

        # Etape 2 : Imprimer dans l'ordre
        imprimer_py = SCRIPT_DIR / "imprimer.py"
        print(f"\n[ETAPE 2/2] Impression de {len(chemins_ordonnes)} PDF...")
        try:
            cmd = [str(self.python_exe), str(imprimer_py)] + chemins_ordonnes
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
        except subprocess.TimeoutExpired:
            print("[ERREUR] Timeout de l'impression (2 min)")
            return
        except Exception as e:
            print(f"[ERREUR] Impression : {e}")
            return

        # Etape 3 : Deplacer les PDF traites vers done
        for pdf in pdfs:
            try:
                dest = self.done / pdf.name
                if dest.exists():
                    dest = self.done / f"{pdf.stem}_{int(time.time())}{pdf.suffix}"
                shutil.move(str(pdf), str(dest))
            except Exception as e:
                print(f"[ERREUR] Deplacement vers done : {e}")

        print(f"\n{'='*50}")
        print(f"[PIPELINE] Termine ! {len(pdfs)} PDF traites et deplaces vers done/")
        print(f"{'='*50}")
        print(f"\n[WATCHER] En attente de nouveaux PDF...\n")


def main():
    dossier_base = DOSSIER_BASE

    # Arguments optionnels
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

    # Creer les dossiers s'ils n'existent pas
    for d in [inbox, processing, done]:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Dossier pret : {d}")

    # Detecter Python
    python_exe = Path(sys.executable)
    print(f"[OK] Python : {python_exe}")
    print(f"[OK] Scripts : {SCRIPT_DIR}")

    handler = PDFHandler(dossier_base, python_exe)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()

    print(f"\n[WATCHER] Surveillance de {inbox}")
    print(f"[WATCHER] Depose des PDF dans ce dossier pour lancer le pipeline.")
    print(f"[WATCHER] Ctrl+C pour arreter.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("\n[WATCHER] Arrete.")


if __name__ == "__main__":
    main()
