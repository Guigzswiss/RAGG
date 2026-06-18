"""
Parsing des fichiers XML Akoma Ntoso (Fedlex) et découpage par article.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import re
import xml.etree.ElementTree as ET


@dataclass
class ArticleChunk:
    law_sr: str          # ex. "642.11"
    law_name: str        # ex. "LIFD"
    article_id: str      # ex. "art. 1"
    text: str
    url: str = ""
    version_date: str = ""
    metadata: dict = field(default_factory=dict)


# Namespaces Akoma Ntoso
_NS = {
    "akn": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0",
    "fmx": "http://formex.publications.europa.eu/formex-files/physical-schema/formex-08.xsd",
}


def _text_of(elem) -> str:
    """Extrait le texte récursif d'un élément XML."""
    parts = []
    if elem.text:
        parts.append(elem.text.strip())
    for child in elem:
        parts.append(_text_of(child))
        if child.tail:
            parts.append(child.tail.strip())
    return " ".join(p for p in parts if p)


def parse_akn_xml(xml_content: str, law_sr: str, law_name: str,
                  url: str = "", version_date: str = "") -> List[ArticleChunk]:
    """Parse un XML Akoma Ntoso Fedlex et retourne un chunk par article."""
    chunks: List[ArticleChunk] = []

    try:
        root = ET.fromstring(xml_content.encode() if isinstance(xml_content, str) else xml_content)
    except ET.ParseError as e:
        raise ValueError(f"XML invalide : {e}") from e

    # Chercher tous les éléments <article> quelle que soit la profondeur
    for tag in ("akn:article", "article"):
        prefix = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}" if "akn:" in tag else ""
        for art in root.iter(f"{prefix}article"):
            art_id = art.get("eId") or art.get("id") or "?"
            text = _text_of(art).strip()
            if not text:
                continue
            chunks.append(ArticleChunk(
                law_sr=law_sr,
                law_name=law_name,
                article_id=art_id,
                text=text,
                url=url,
                version_date=version_date,
            ))
        if chunks:
            break

    return chunks


def parse_sample(sample_articles: list[dict], law_sr: str, law_name: str) -> List[ArticleChunk]:
    """Convertit des dicts d'articles échantillons en ArticleChunks."""
    chunks = []
    for a in sample_articles:
        chunks.append(ArticleChunk(
            law_sr=law_sr,
            law_name=law_name,
            article_id=a.get("id", "?"),
            text=a.get("text", ""),
            url=a.get("url", ""),
            version_date=a.get("version_date", ""),
        ))
    return chunks
