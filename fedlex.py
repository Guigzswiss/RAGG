"""
Ingestion du droit fédéral suisse depuis Fedlex (SPARQL + XML Akoma Ntoso).
"""
from __future__ import annotations
from typing import List
from parse_chunk import ArticleChunk, parse_akn_xml, parse_sample

# ── Échantillon LIFD pour les tests hors-ligne ────────────────────────────────
SAMPLE_LIFD = [
    {
        "id": "art. 1",
        "text": (
            "La Confédération perçoit un impôt sur le revenu des personnes physiques. "
            "Sont assujetties à cet impôt les personnes physiques qui ont leur domicile "
            "ou leur séjour en Suisse au regard du droit fiscal."
        ),
        "url": "https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2024-01-01",
    },
    {
        "id": "art. 16",
        "text": (
            "Sont imposables tous les revenus du contribuable, qu'ils soient uniques ou récurrents. "
            "Sont aussi considérés comme revenu les prestations en nature de toute espèce dont bénéficie "
            "le contribuable, notamment la pension et le logement, ainsi que les produits et "
            "marchandises qu'il prélève dans son exploitation commerciale et qui sont destinés à sa "
            "consommation personnelle; ces prestations sont estimées à leur valeur marchande."
        ),
        "url": "https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2024-01-01",
    },
    {
        "id": "art. 33",
        "text": (
            "Sont déduits du revenu: les intérêts passifs privés à concurrence du rendement imposable "
            "de la fortune et de 50 000 francs supplémentaires; les rentes viagères et les charges "
            "permanentes; les pensions alimentaires versées au conjoint divorcé ou séparé judiciairement "
            "ou de fait ainsi que les contributions d'entretien versées à l'un des parents pour les "
            "enfants sur lesquels il a l'autorité parentale."
        ),
        "url": "https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2024-01-01",
    },
    {
        "id": "art. 49",
        "text": (
            "Les sociétés de capitaux (sociétés anonymes, sociétés en commandite par actions, "
            "sociétés à responsabilité limitée) et les sociétés coopératives sont imposables "
            "d'après la présente loi. Il en va de même pour les associations, fondations et "
            "autres personnes morales."
        ),
        "url": "https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2024-01-01",
    },
    {
        "id": "art. 57",
        "text": (
            "L'impôt sur le bénéfice a pour objet le bénéfice net. "
            "Le bénéfice net imposable comprend: le solde du compte de résultats, compte tenu "
            "du solde reporté de l'exercice précédent; tous les prélèvements opérés avant le calcul "
            "du solde du compte de résultats qui ne servent pas à couvrir des dépenses justifiées "
            "par l'usage commercial."
        ),
        "url": "https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2024-01-01",
    },
]


def load_sample_lifd() -> List[ArticleChunk]:
    """Retourne l'échantillon LIFD sous forme de chunks."""
    return parse_sample(SAMPLE_LIFD, law_sr="642.11", law_name="LIFD")


def fetch_law_from_fedlex(sr: str) -> List[ArticleChunk]:
    """
    Télécharge une loi depuis Fedlex via SPARQL puis parse le XML Akoma Ntoso.
    Requiert une connexion internet.
    """
    import urllib.request
    import urllib.parse
    import json
    from config import FEDLEX_SPARQL

    # 1. Trouver l'URI de la dernière version consolidée via SPARQL
    sparql_query = f"""
    PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
    PREFIX schema: <http://schema.org/>
    SELECT ?expression ?title WHERE {{
      ?work jolux:classifiedByTaxonomyEntry <https://fedlex.admin.ch/vocabulary/legal-taxonomy/{sr}> ;
            jolux:hasExpression ?expression .
      ?expression jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
                  schema:name ?title .
    }}
    LIMIT 1
    """
    params = urllib.parse.urlencode({
        "query": sparql_query,
        "format": "application/sparql-results+json"
    })
    req = urllib.request.Request(
        f"{FEDLEX_SPARQL}?{params}",
        headers={"Accept": "application/sparql-results+json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        raise ValueError(f"Aucune expression trouvée pour SR {sr}")

    expression_uri = bindings[0]["expression"]["value"]
    title = bindings[0].get("title", {}).get("value", sr)

    # 2. Construire l'URL du XML Akoma Ntoso
    xml_url = expression_uri.replace("/eli/", "/filestore/fedlex.data.admin.ch/eli/") + "/akn/fr/xml"

    req2 = urllib.request.Request(xml_url, headers={"Accept": "application/xml"})
    with urllib.request.urlopen(req2, timeout=60) as resp:
        xml_content = resp.read().decode("utf-8")

    return parse_akn_xml(
        xml_content,
        law_sr=sr,
        law_name=title,
        url=expression_uri,
        version_date="",
    )
