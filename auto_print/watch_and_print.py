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
import subprocess
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
PRINT_TIMEOUT_SECONDS = 30

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff"}
PDF_EXTENSIONS = {".pdf"}
OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS | OFFICE_EXTENSIONS

# SumatraPDF.exe (portable, gratuit) place a cote de ce script permet une impression
# PDF totalement silencieuse. S'il est absent, on retombe sur le verbe "print" de
# Windows (qui peut ouvrir l'appli associee).
SUMATRA_PATH = Path(__file__).resolve().parent / "SumatraPDF.exe"

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


def get_default_printer() -> str:
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "(Get-CimInstance -ClassName Win32_Printer | Where-Object { $_.Default }).Name",
        ],
        capture_output=True, text=True, timeout=15, check=True,
    )
    name = result.stdout.strip()
    if not name:
        raise RuntimeError("Impossible de determiner l'imprimante par defaut.")
    return name


def print_file(path: Path) -> None:
    """Imprime sans afficher de fenetre, avec la methode la plus fiable pour chaque type de fichier."""
    extension = path.suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        # mspaint sait imprimer une image en silence, sans assistant, via /pt.
        printer = get_default_printer()
        subprocess.run(
            ["mspaint.exe", "/pt", str(path), printer],
            check=True, timeout=PRINT_TIMEOUT_SECONDS,
        )
        return

    if extension in PDF_EXTENSIONS and SUMATRA_PATH.exists():
        subprocess.run(
            [str(SUMATRA_PATH), "-print-to-default", "-silent", "-exit-when-done", str(path)],
            check=True, timeout=PRINT_TIMEOUT_SECONDS,
        )
        return

    # PDF sans SumatraPDF, ou document Office : on utilise le verbe "print" de Windows,
    # qui declenche l'application associee (peut s'ouvrir brievement).
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
