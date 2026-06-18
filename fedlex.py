"""
Ingestion du droit fédéral suisse depuis Fedlex (SPARQL + XML Akoma Ntoso).

Endpoint SPARQL : https://fedlex.data.admin.ch/sparqlendpoint  (Virtuoso)
Modèle RDF     : Work → Consolidation (version datée) → Expression (langue)
                 → Manifestation (format) → isExemplifiedBy (URL du fichier)
"""
from __future__ import annotations
from typing import List
from parse_chunk import ArticleChunk, parse_akn_xml, parse_sample

# ── Endpoint correct (fedlex.data.admin.ch, pas fedlex.admin.ch) ──────────────
FEDLEX_SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "gsass-rag/1.0 (fiduciaire genevoise; contact: guillaume.droz06@gmail.com)"

# ── Échantillon LIFD pour les tests hors-ligne ────────────────────────────────
SAMPLE_LIFD = [
    {
        "id": "art. 1",
        "text": (
            "La Confédération perçoit un impôt sur le revenu des personnes physiques. "
            "Sont assujetties à cet impôt les personnes physiques qui ont leur domicile "
            "ou leur séjour en Suisse au regard du droit fiscal."
        ),
        "url": "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2026-01-01",
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
        "url": "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2026-01-01",
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
        "url": "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2026-01-01",
    },
    {
        "id": "art. 49",
        "text": (
            "Les sociétés de capitaux (sociétés anonymes, sociétés en commandite par actions, "
            "sociétés à responsabilité limitée) et les sociétés coopératives sont imposables "
            "d'après la présente loi. Il en va de même pour les associations, fondations et "
            "autres personnes morales."
        ),
        "url": "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2026-01-01",
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
        "url": "https://fedlex.data.admin.ch/eli/cc/1991/1184_1184_1184/fr",
        "version_date": "2026-01-01",
    },
]


def load_sample_lifd() -> List[ArticleChunk]:
    """Retourne l'échantillon LIFD sous forme de chunks (test hors-ligne)."""
    return parse_sample(SAMPLE_LIFD, law_sr="642.11", law_name="LIFD")


def _sparql_query(query: str) -> list:
    """Exécute une requête SPARQL sur fedlex.data.admin.ch et retourne les bindings."""
    import urllib.request
    import urllib.parse
    import json

    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(
        FEDLEX_SPARQL,
        data=data,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result["results"]["bindings"]


def fetch_law_from_fedlex(sr: str) -> List[ArticleChunk]:
    """
    Télécharge la dernière version consolidée d'une loi fédérale depuis Fedlex.

    Paramètre :
        sr  Numéro SR, ex. "642.11" pour la LIFD.

    Retourne une liste d'ArticleChunk (un par article).
    """
    import urllib.request

    # ── Étape 1 : trouver l'URL du fichier XML via SPARQL ─────────────────────
    # Modèle : Work (historicalLegalId=SR) → Consolidation (version datée)
    #          → Expression (FR) → Manifestation (XML) → isExemplifiedBy (URL)
    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?version ?title ?xml_url WHERE {{
  ?work jolux:historicalLegalId "{sr}" ;
        jolux:isRealizedBy ?base_expr .
  ?base_expr jolux:language <http://publications.europa.eu/resource/authority/language/FRA> .
  OPTIONAL {{ ?base_expr jolux:title ?title }}
  ?version jolux:isMemberOf ?work ;
           jolux:isRealizedBy ?expr .
  ?expr jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ;
        jolux:isEmbodiedBy ?manif .
  ?manif jolux:userFormat <https://fedlex.data.admin.ch/vocabulary/user-format/xml> ;
         jolux:isExemplifiedBy ?xml_url .
}}
ORDER BY DESC(?version)
LIMIT 1
"""
    bindings = _sparql_query(query)
    if not bindings:
        raise ValueError(
            f"Aucune version XML trouvée pour SR {sr}. "
            "Vérifiez le numéro SR (ex. '642.11') et la connexion."
        )

    xml_url = bindings[0]["xml_url"]["value"]
    title = bindings[0].get("title", {}).get("value", f"SR {sr}")
    version_uri = bindings[0].get("version", {}).get("value", "")
    version_date = version_uri.split("/")[-1] if version_uri else ""
    # Formater la date : "20260101" → "2026-01-01"
    if len(version_date) == 8 and version_date.isdigit():
        version_date = f"{version_date[:4]}-{version_date[4:6]}-{version_date[6:]}"

    canonical_url = f"https://fedlex.data.admin.ch/eli/cc/{version_uri.split('/eli/cc/')[-1].rstrip('/fr/xml')}" if "/eli/cc/" in version_uri else version_uri

    print(f"  Loi       : {title} (SR {sr})")
    print(f"  Version   : {version_date}")
    print(f"  Fichier   : {xml_url}")

    # ── Étape 2 : télécharger le fichier XML ───────────────────────────────────
    req = urllib.request.Request(
        xml_url,
        headers={"Accept": "application/xml, */*", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        xml_content = resp.read().decode("utf-8", errors="replace")

    print(f"  XML       : {len(xml_content)} caractères téléchargés")

    # ── Étape 3 : parser le XML Akoma Ntoso ───────────────────────────────────
    return parse_akn_xml(
        xml_content,
        law_sr=sr,
        law_name=title,
        url=canonical_url,
        version_date=version_date,
    )
