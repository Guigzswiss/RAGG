"""
Parsing de PDFs juridiques locaux :
  - Lois cantonales genevoises (ge.ch/legi)
  - Lois cantonales vaudoises (vd.ch)
  - Circulaires AFC (estv.admin.ch)
  - Tout autre PDF structuré par articles ou sections numérotées

Nécessite : pip install pdfplumber
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import List
from parse_chunk import ArticleChunk

# ── Détection automatique des lois cantonales ─────────────────────────────────
_LAW_HINTS = {
    # Genève — fiscalité
    "lipp": ("D 3 08", "LIPP"),
    "imposition des personnes physiques": ("D 3 08", "LIPP"),
    "lipm": ("D 3 15", "LIPM"),
    "imposition des personnes morales": ("D 3 15", "LIPM"),
    "lpfisc": ("D 3 17", "LPFisc"),
    "procédure fiscale": ("D 3 17", "LPFisc"),
    "lcp": ("D 3 05", "LCP"),
    "contributions publiques": ("D 3 05", "LCP"),
    "centimes additionnels cantonaux": ("D 3 07", "LCACant"),
    "lcacant": ("D 3 07", "LCACant"),
    "lefi": ("D 3 10", "LEFI"),
    "exonérations fiscales": ("D 3 10", "LEFI"),
    "lpgip": ("D 3 18", "LPGIP"),
    "perception et garanties": ("D 3 18", "LPGIP"),
    "lisp": ("D 3 20", "LISP"),
    "impôt à la source": ("D 3 20", "LISP"),
    "lds": ("D 3 25", "LDS"),
    "droits de succession": ("D 3 25", "LDS"),
    "lde": ("D 3 30", "LDE"),
    "droits d'enregistrement": ("D 3 30", "LDE"),
    "lmsd": ("D 3 30", "LDE"),
    # Genève — autres
    "lrcv": ("B 6 09", "LRCV"),
    "redevance": ("B 6 09", "LRCV"),
    # Vaud
    "impôts directs cantonaux": ("RSV 642.11", "LI-VD"),
    "li vd": ("RSV 642.11", "LI-VD"),
    "648.11": ("RSV 648.11", "LHR-VD"),
}

# ── Patterns de découpage ─────────────────────────────────────────────────────

# Articles de loi : Art. 1, Art. 16a, Art. 205bis
_ART_RE = re.compile(
    r"^art(?:icle)?\.?\s+(\d+\s*[a-z]?(?:\s*(?:bis|ter|quater|quinquies))?)\b",
    re.IGNORECASE,
)

# Circulaires AFC — sections numérotées : "1.", "1.1", "2.3.4", "I.", "II."
_CIRC_SECTION_RE = re.compile(
    r"^(\d+(?:\.\d+)*\.?|[IVX]{1,5}\.)\s+(.+)$"
)

# Détection circulaire AFC dans le texte
# "n° 39", "no. 39", "n 39a" : le point après "no" et un suffixe de lettre
# (199a) sont tolérés.
_CIRC_RE = re.compile(
    r"circulaire\s+n[o°]?\.?\s*(\d+[a-z]?)",
    re.IGNORECASE,
)
_CIRC_DATE_RE = re.compile(
    r"circulaire\s+n[o°]?\.?\s*(\d+[a-z]?)\s+du\s+(.+?)(?:\n|—|-|–)",
    re.IGNORECASE,
)
# Numéro depuis le nom de fichier : "AFC_CIRC_155.pdf", "AFC-CIRC-199a.pdf".
# Source la plus fiable : beaucoup de "Lettre circulaire" n'ont aucun numéro
# dans leur en-tête, mais le fichier est toujours nommé AFC_CIRC_<num>.
_CIRC_FILENAME_RE = re.compile(
    r"AFC[_\- ]?CIRC[_\- ]?(\d+[a-z]?)",
    re.IGNORECASE,
)


def _detect_afc_circular(text: str, filename: str = "") -> tuple[str, str] | None:
    """Retourne (ref, name) si le PDF est une circulaire AFC, sinon None.

    Le numéro est lu en priorité depuis le nom de fichier (AFC_CIRC_<num>),
    puis depuis l'en-tête. Le repli "AFC-Circ-?" ne sert plus que pour un
    PDF de circulaire ni nommé ni numéroté dans son en-tête.
    """
    # 1. Numéro depuis le nom de fichier (le plus fiable)
    if filename:
        mf = _CIRC_FILENAME_RE.search(filename)
        if mf:
            num = mf.group(1).lower()
            return f"AFC-Circ-{num}", f"Circulaire AFC n° {num}"

    header = text[:2000]
    # 2. "Circulaire n° X du <date>"
    m_full = _CIRC_DATE_RE.search(header)
    if m_full:
        num = m_full.group(1).lower()
        return f"AFC-Circ-{num}", f"Circulaire AFC n° {num}"
    # 3. "Circulaire n° X" / "Circulaire no. X"
    m = _CIRC_RE.search(header)
    if m:
        num = m.group(1).lower()
        return f"AFC-Circ-{num}", f"Circulaire AFC n° {num}"
    # 4. Repli : PDF AFC clairement circulaire mais numéro illisible
    lower = header.lower()
    if "administration fédérale des contributions" in lower or "afc" in lower:
        if "circulaire" in lower or "kreisschreiben" in lower or "circolare" in lower:
            return "AFC-Circ-?", "Circulaire AFC"
    return None


def _detect_law(text: str, filename: str = "") -> tuple[str, str]:
    """Devine la référence et le nom depuis le texte brut, puis le nom de fichier."""
    lower = text[:3000].lower()
    for hint, (ref, name) in _LAW_HINTS.items():
        if hint in lower:
            return ref, name

    # Fallback : extraire la référence depuis le nom de fichier
    # Ex: "D3_07_LCACant.pdf" → ("D 3 07", "LCACant")
    # Ex: "B6_09_LRCV.pdf"   → ("B 6 09", "LRCV")
    if filename:
        stem = Path(filename).stem  # "D3_07_LCACant"
        parts = stem.split("_")
        if len(parts) >= 3:
            # Reconstituer la référence : "D3" → "D 3", "07" → "07"
            prefix = parts[0]  # "D3" ou "B6"
            number = parts[1]  # "07"
            law_name = "_".join(parts[2:])  # "LCACant"
            # Insérer espace dans le préfixe lettres+chiffres : "D3" → "D 3"
            import re as _re
            prefix_fmt = _re.sub(r"([A-Z]+)(\d+)", r"\1 \2", prefix)
            ref = f"{prefix_fmt} {number}"
            return ref, law_name

    return "GE-INCONNU", "Loi GE"


def _parse_by_articles(lines: list[str], law_ref: str, law_name: str,
                        url: str) -> List[ArticleChunk]:
    """Découpe par articles (Art. N)."""
    chunks: List[ArticleChunk] = []
    current_art: str | None = None
    current_lines: list[str] = []

    def flush():
        if current_art and current_lines:
            text = " ".join(" ".join(current_lines).split())
            if len(text) > 20:
                chunks.append(ArticleChunk(
                    law_sr=law_ref, law_name=law_name,
                    article_id=current_art, text=text,
                    url=url, version_date="",
                ))

    for line in lines:
        stripped = line.strip()
        m = _ART_RE.match(stripped)
        if m:
            flush()
            current_art = "art. " + m.group(1).strip().lower()
            rest = stripped[m.end():].strip()
            current_lines = [rest] if rest else []
        elif current_art is not None:
            if stripped and not re.match(r"^\d+$", stripped) and len(stripped) > 3:
                current_lines.append(stripped)

    flush()
    return chunks


def _parse_circular(lines: list[str], law_ref: str, law_name: str,
                    url: str) -> List[ArticleChunk]:
    """
    Découpe une circulaire AFC par sections numérotées (1., 1.1, 2.3, etc.)
    Chaque section de niveau 1 ou 2 devient un chunk.
    """
    chunks: List[ArticleChunk] = []
    current_id: str | None = None
    current_title: str = ""
    current_lines: list[str] = []

    def flush():
        if current_id and current_lines:
            text = current_title + " " + " ".join(" ".join(current_lines).split())
            text = text.strip()
            if len(text) > 30:
                chunks.append(ArticleChunk(
                    law_sr=law_ref, law_name=law_name,
                    article_id=current_id, text=text,
                    url=url, version_date="",
                ))

    for line in lines:
        stripped = line.strip()
        if not stripped or re.match(r"^\d+$", stripped):
            continue
        m = _CIRC_SECTION_RE.match(stripped)
        if m:
            num = m.group(1).rstrip(".")
            # Rejeter les faux positifs : codes postaux (3003 Berne),
            # numéros de page, codes internes AFC (090, 112a).
            # Un vrai numéro de section de niveau 1 ne dépasse pas 99.
            top_level = num.split(".")[0] if "." in num else num
            if top_level.isdigit() and (int(top_level) > 99
                                        or (len(top_level) > 1
                                            and top_level[0] == "0")):
                if current_id is not None:
                    current_lines.append(stripped)
                continue
            depth = num.count(".") + 1 if "." in num else 1
            if depth <= 2:
                flush()
                current_id = f"§ {num}"
                current_title = m.group(2).strip()
                current_lines = []
            elif current_id is not None:
                current_lines.append(stripped)
        elif current_id is not None:
            current_lines.append(stripped)

    flush()

    # Fallback : si trop peu de sections détectées, essayer par articles
    if len(chunks) < 3:
        return _parse_by_articles(lines, law_ref, law_name, url)

    return chunks


def _chunk_raw_text(text: str, law_ref: str, law_name: str, url: str,
                    max_chars: int = 1500) -> List[ArticleChunk]:
    """Repli sans perte : découpe un texte brut en parties de taille bornée.

    Utilisé quand ni le découpage par sections ni par articles ne produit
    de chunk (sinon le document entier serait perdu). On coupe sur des
    frontières de mots, donc rien n'est tronqué.
    """
    words = text.split()
    chunks: List[ArticleChunk] = []
    buf: list[str] = []
    size = 0
    part = 1

    def flush():
        nonlocal buf, size, part
        if buf:
            chunks.append(ArticleChunk(
                law_sr=law_ref, law_name=law_name,
                article_id=f"partie {part}", text=" ".join(buf),
                url=url, version_date="",
            ))
            buf, size, part = [], 0, part + 1

    for w in words:
        buf.append(w)
        size += len(w) + 1
        if size >= max_chars:
            flush()
    flush()
    return chunks


def parse_pdf(pdf_path: Path) -> List[ArticleChunk]:
    """
    Parse un PDF juridique (loi cantonale ou circulaire AFC).
    Détecte automatiquement le type et adapte le découpage.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pip install pdfplumber")

    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [p.extract_text() for p in pdf.pages if p.extract_text()]

    full_text = "\n".join(pages_text)
    lines = full_text.splitlines()

    # 1. Circulaire AFC ?
    circ = _detect_afc_circular(full_text, pdf_path.name)
    if circ:
        law_ref, law_name = circ
        url = "https://www.estv.admin.ch/estv/fr/home/direkt-bundessteuer/fachinformationen/kreisschreiben.html"
        chunks = _parse_circular(lines, law_ref, law_name, url)
        # Repli : circulaire sans section ni article détectés (sinon perdue)
        if not chunks:
            chunks = _chunk_raw_text(full_text, law_ref, law_name, url)
        return chunks

    # 2. Loi cantonale
    law_ref, law_name = _detect_law(full_text, pdf_path.name)
    if law_ref.startswith("D ") or law_ref.startswith("RSV"):
        canton = "ge" if law_ref.startswith("D ") else "vd"
        url = f"https://www.{'ge' if canton == 'ge' else 'vd'}.ch/legi/{law_ref.replace(' ', '-')}"
    else:
        url = ""

    chunks = _parse_by_articles(lines, law_ref, law_name, url)

    # Fallback texte brut si rien trouvé
    if not chunks:
        text = " ".join(full_text.split())
        if text:
            name = pdf_path.stem
            chunks = [ArticleChunk(
                law_sr=name, law_name=name,
                article_id="complet", text=text[:6000],
                url=url, version_date="",
            )]

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
            print(f"  Chunks  : {len(chunks)} extraits")
            if chunks:
                print(f"  Type    : {chunks[0].law_name} ({chunks[0].law_sr})")
                print(f"  Premier : {chunks[0].article_id}")
            results[pdf_path.name] = chunks
        except Exception as e:
            print(f"  ERREUR  : {e}")
            results[pdf_path.name] = []

    return results
