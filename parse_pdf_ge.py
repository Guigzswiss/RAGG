"""
Parsing des lois cantonales genevoises depuis des fichiers PDF locaux.
Nécessite : pip install pdfplumber
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List
from parse_chunk import ArticleChunk

# Détection automatique loi/nom depuis le texte du PDF
_LAW_HINTS = {
    "lipp": ("D 3 08", "LIPP"),
    "imposition des personnes physiques": ("D 3 08", "LIPP"),
    "lipm": ("D 3 15", "LIPM"),
    "imposition des personnes morales": ("D 3 15", "LIPM"),
    "lpfisc": ("D 3 17", "LPFisc"),
    "procédure fiscale": ("D 3 17", "LPFisc"),
    "lmsd": ("D 3 30", "LMSD"),
    "droits de succession": ("D 3 30", "LMSD"),
    "succession": ("D 3 30", "LMSD"),
    "lcp": ("D 3 05", "LCP"),
    "contributions publiques": ("D 3 05", "LCP"),
}

_ART_RE = re.compile(
    r"^art(?:icle)?\.?\s+(\d+\s*[a-z]?(?:\s*(?:bis|ter|quater|quinquies))?)\b",
    re.IGNORECASE,
)


def _detect_law(text: str) -> tuple[str, str]:
    """Devine la référence et le nom de la loi depuis le texte brut."""
    lower = text[:3000].lower()
    for hint, (ref, name) in _LAW_HINTS.items():
        if hint in lower:
            return ref, name
    return "GE-INCONNU", "Loi GE"


def parse_pdf(pdf_path: Path) -> List[ArticleChunk]:
    """Parse un PDF de loi genevoise et retourne un chunk par article."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pip install pdfplumber")

    with pdfplumber.open(pdf_path) as pdf:
        pages_text = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)

    full_text = "\n".join(pages_text)
    law_ref, law_name = _detect_law(full_text)
    url = f"https://www.ge.ch/document/{law_ref.replace(' ', '-')}/consulter"

    # Découper par article
    lines = full_text.splitlines()
    chunks: List[ArticleChunk] = []
    current_art: str | None = None
    current_lines: list[str] = []

    def flush():
        if current_art and current_lines:
            text = " ".join(" ".join(current_lines).split())
            if len(text) > 20:
                chunks.append(ArticleChunk(
                    law_sr=law_ref,
                    law_name=law_name,
                    article_id=current_art,
                    text=text,
                    url=url,
                    version_date="",
                ))

    for line in lines:
        stripped = line.strip()
        m = _ART_RE.match(stripped)
        if m:
            flush()
            current_art = "art. " + m.group(1).strip().lower()
            # Texte sur la même ligne après le numéro d'article
            rest = stripped[m.end():].strip()
            current_lines = [rest] if rest else []
        elif current_art is not None:
            # Ignorer les lignes de pagination (numéro seul, entêtes courts)
            if stripped and not re.match(r"^\d+$", stripped) and len(stripped) > 3:
                current_lines.append(stripped)

    flush()
    return chunks


def parse_pdf_folder(folder: str | Path) -> dict[str, List[ArticleChunk]]:
    """Parse tous les PDFs d'un dossier. Retourne {filename: chunks}."""
    folder = Path(folder)
    results = {}
    pdfs = list(folder.glob("*.pdf"))
    if not pdfs:
        print(f"  Aucun PDF trouvé dans {folder}")
        return results

    for pdf_path in sorted(pdfs):
        print(f"\n  Parsing : {pdf_path.name}")
        try:
            chunks = parse_pdf(pdf_path)
            print(f"  Articles : {len(chunks)} extraits")
            if chunks:
                print(f"  Loi      : {chunks[0].law_name} ({chunks[0].law_sr})")
            results[pdf_path.name] = chunks
        except Exception as e:
            print(f"  ERREUR   : {e}")
            results[pdf_path.name] = []

    return results
