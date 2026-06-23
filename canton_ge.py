"""
Ingestion des lois cantonales genevoises depuis ge.ch/legi (HTML).

Chaque loi est identifiée par sa référence genevoise (ex. "D 3 08").
Le site ge.ch/legi retourne du HTML qu'on parse avec html.parser (stdlib).
"""
from __future__ import annotations
from typing import List
from parse_chunk import ArticleChunk

# User-Agent de navigateur : ge.ch renvoie 403 sur les UA non-navigateur.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Lois cantonales genevoises fiscales (convention alignée sur parse_pdf_ge._LAW_HINTS)
LOIS_GE = {
    "D 3 05":  "LCP",     # Loi générale sur les contributions publiques
    "D 3 07":  "LCACant", # Centimes additionnels cantonaux
    "D 3 08":  "LIPP",    # Imposition des personnes physiques
    "D 3 10":  "LEFI",    # Exonérations fiscales
    "D 3 15":  "LIPM",    # Imposition des personnes morales
    "D 3 17":  "LPFisc",  # Procédure fiscale
    "D 3 18":  "LPGIP",   # Perception et garanties des impôts des personnes physiques
    "D 3 20":  "LISP",    # Impôt à la source
    "D 3 25":  "LDS",     # Droits de succession
    "D 3 30":  "LDE",     # Droits d'enregistrement
}


def _ge_url(ref: str) -> str:
    """URL canonique d'affichage (stockée comme source dans les chunks)."""
    slug = ref.replace(" ", "-")
    return f"https://www.ge.ch/legislation/rsg/f/s/rsg_{slug.lower().replace('-', '')}.html"


def _candidate_urls(ref: str) -> list[str]:
    """Plusieurs formats d'URL ge.ch/SILGENEVE à essayer dans l'ordre.

    Ex. "D 3 08" → rsg_d3_08. Le site renvoie 403/404 selon les formats,
    on essaie donc successivement jusqu'à obtenir une page substantielle.
    """
    parts = ref.split()           # ["D", "3", "08"]
    letter = parts[0].lower()     # "d"
    rest = "".join(parts[1:])     # "308"
    tail = "_".join(parts[1:])    # "3_08"
    code = f"{letter}{parts[1]}_{parts[2]}" if len(parts) >= 3 else f"{letter}{rest}"
    slug = ref.replace(" ", "-")
    return [
        f"https://www.ge.ch/legislation/rsg/f/s/rsg_{code}.html",
        f"https://www.ge.ch/legislation/rsg/f/rsg_{code}.html",
        f"https://silgeneve.ch/legis/program/books/rsg/htm/rsg_{code}.htm",
        f"https://www.ge.ch/document/{slug}/consulter",
    ]


def _fetch_html(url: str) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-CH,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _fetch_first_ok(ref: str) -> tuple[str, str]:
    """Essaie chaque URL candidate, retourne (html, url) du premier succès."""
    import urllib.error
    last_err = None
    for u in _candidate_urls(ref):
        try:
            html = _fetch_html(u)
            if len(html) > 2000:   # page substantielle
                return html, u
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            last_err = e
            continue
    raise RuntimeError(f"Aucune URL ge.ch accessible pour {ref} (dernier: {last_err})")


def _parse_ge_html(html: str, law_ref: str, law_name: str, url: str) -> List[ArticleChunk]:
    """
    Parse le HTML de ge.ch/legi et extrait les articles.
    Les articles sont dans des <div> ou <p> précédés d'un titre "Art. N".
    """
    from html.parser import HTMLParser
    import re

    class GeParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks: List[ArticleChunk] = []
            self._current_art: str | None = None
            self._current_text: list[str] = []
            self._capture = False
            self._depth = 0
            self._art_pattern = re.compile(
                r"^art(?:icle)?\.?\s*(\d+\s*[a-z]?(?:\s*bis|ter|quater)?)",
                re.IGNORECASE,
            )

        def _flush(self):
            if self._current_art and self._current_text:
                text = " ".join(" ".join(self._current_text).split())
                if text:
                    self.chunks.append(ArticleChunk(
                        law_sr=law_ref,
                        law_name=law_name,
                        article_id=self._current_art,
                        text=text,
                        url=url,
                        version_date="",
                    ))
            self._current_art = None
            self._current_text = []

        def handle_starttag(self, tag, attrs):
            if self._capture:
                self._depth += 1

        def handle_endtag(self, tag):
            if self._capture and self._depth > 0:
                self._depth -= 1
                if self._depth == 0:
                    self._capture = False

        def handle_data(self, data):
            stripped = data.strip()
            if not stripped:
                return
            m = self._art_pattern.match(stripped)
            if m:
                self._flush()
                self._current_art = "art. " + m.group(1).strip().lower()
                self._capture = True
                self._depth = 0
            elif self._current_art is not None:
                self._current_text.append(stripped)

        def close(self):
            self._flush()
            super().close()

    parser = GeParser()
    parser.feed(html)
    parser.close()
    return parser.chunks


def _parse_ge_html_fallback(html: str, law_ref: str, law_name: str, url: str) -> List[ArticleChunk]:
    """
    Fallback : extrait le texte brut et découpe sur les marqueurs 'Art. N'.
    Utilisé quand le parser HTML ne trouve rien (structure inattendue).
    """
    import re
    from html.parser import HTMLParser

    # Extraire le texte brut
    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts: list[str] = []
        def handle_data(self, data):
            s = data.strip()
            if s:
                self.parts.append(s)

    ex = TextExtractor()
    ex.feed(html)
    raw = " ".join(ex.parts)

    # Découper sur Art. N / Article N
    pattern = re.compile(r"\b(Art(?:icle)?\.?\s+\d+\s*[a-z]?(?:\s*bis|ter|quater)?)\b", re.IGNORECASE)
    parts = pattern.split(raw)

    chunks = []
    i = 1
    while i < len(parts) - 1:
        art_id = "art. " + re.sub(r"[Aa]rt(?:icle)?\.?\s*", "", parts[i]).strip().lower()
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        text = " ".join(text.split())
        if text:
            chunks.append(ArticleChunk(
                law_sr=law_ref,
                law_name=law_name,
                article_id=art_id,
                text=text,
                url=url,
                version_date="",
            ))
        i += 2

    return chunks


def fetch_law_from_ge(ref: str, name: str | None = None) -> List[ArticleChunk]:
    """
    Télécharge et parse une loi cantonale genevoise depuis ge.ch/legi.

    Paramètre :
        ref   Référence genevoise, ex. "D 3 08"
        name  Nom court optionnel, ex. "LIPP"
    """
    law_name = name or LOIS_GE.get(ref, ref)

    print(f"  Loi GE     : {law_name} ({ref})")
    html, url = _fetch_first_ok(ref)
    print(f"  URL        : {url}")
    print(f"  HTML       : {len(html)} caractères téléchargés")

    chunks = _parse_ge_html(html, law_ref=ref, law_name=law_name, url=url)

    if len(chunks) < 3:
        print("  Parser HTML: peu de résultats, tentative fallback...")
        chunks = _parse_ge_html_fallback(html, law_ref=ref, law_name=law_name, url=url)

    print(f"  Articles   : {len(chunks)} extraits")
    return chunks
