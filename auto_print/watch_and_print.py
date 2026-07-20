"""
Surveille un dossier et imprime automatiquement chaque nouveau fichier qui y est
depose (PDF, images, documents Office), sur l'imprimante par defaut de Windows.

Utilisation :
    python watch_and_print.py
    python watch_and_print.py "C:\\Users\\moi\\Desktop\\A imprimer"

Le dossier par defaut est Desktop\\A imprimer. Les fichiers traites sont deplaces
dans un sous-dossier "Imprimes", "Erreurs" ou "Non supportes" selon le resultat.
"""

import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────
WATCH_FOLDER = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "A imprimer"
PRINTED_SUBFOLDER = "Imprimes"
ERROR_SUBFOLDER = "Erreurs"
IGNORED_SUBFOLDER = "Non supportes"
POLL_INTERVAL_SECONDS = 2
STABLE_CHECKS = 2  # verifications consecutives a taille identique avant de traiter le fichier
MAX_STABILITY_WAIT_SECONDS = 30

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}

LOG_FILE = WATCH_FOLDER / "auto_print.log"


def setup_logging() -> None:
    WATCH_FOLDER.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def ensure_subfolders() -> tuple[Path, Path, Path]:
    printed = WATCH_FOLDER / PRINTED_SUBFOLDER
    errors = WATCH_FOLDER / ERROR_SUBFOLDER
    ignored = WATCH_FOLDER / IGNORED_SUBFOLDER
    for folder in (printed, errors, ignored):
        folder.mkdir(parents=True, exist_ok=True)
    return printed, errors, ignored


def is_file_stable(path: Path) -> bool:
    """Attend que la taille du fichier arrete de bouger (copie/telechargement termine)."""
    last_size = -1
    stable_count = 0
    waited = 0
    while waited < MAX_STABILITY_WAIT_SECONDS:
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last_size:
            stable_count += 1
            if stable_count >= STABLE_CHECKS:
                return True
        else:
            stable_count = 0
        last_size = size
        time.sleep(1)
        waited += 1
    return False


def unique_destination(folder: Path, name: str) -> Path:
    destination = folder / name
    if not destination.exists():
        return destination
    stem, suffix = Path(name).stem, Path(name).suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return folder / f"{stem}_{timestamp}{suffix}"


def print_file(path: Path) -> None:
    """Lance l'impression via l'application associee et l'imprimante par defaut de Windows."""
    os.startfile(str(path), "print")


def process_file(path: Path, printed_dir: Path, error_dir: Path, ignored_dir: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        destination = unique_destination(ignored_dir, path.name)
        shutil.move(str(path), str(destination))
        logging.warning("Type non supporte, deplace sans impression : %s", path.name)
        return

    if not is_file_stable(path):
        logging.error("Le fichier n'est jamais devenu stable, on reessaiera au prochain passage : %s", path.name)
        return

    destination = unique_destination(printed_dir, path.name)
    try:
        shutil.move(str(path), str(destination))
        print_file(destination)
        logging.info("Envoye a l'impression : %s", destination.name)
    except Exception as exc:
        error_destination = unique_destination(error_dir, path.name)
        try:
            shutil.move(str(destination), str(error_destination))
        except Exception:
            pass
        logging.exception("Echec de l'impression de %s : %s", path.name, exc)


def main() -> None:
    setup_logging()
    printed_dir, error_dir, ignored_dir = ensure_subfolders()
    skip_paths = {printed_dir, error_dir, ignored_dir, LOG_FILE}

    logging.info("Surveillance du dossier : %s", WATCH_FOLDER)

    while True:
        try:
            for entry in sorted(WATCH_FOLDER.iterdir()):
                if entry in skip_paths or entry.is_dir():
                    continue
                process_file(entry, printed_dir, error_dir, ignored_dir)
        except Exception:
            logging.exception("Erreur pendant le scan du dossier")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
