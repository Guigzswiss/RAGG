"""
Audit qualité des métadonnées de la base ChromaDB (LECTURE SEULE).

Ne modifie rien. Répond à 3 questions :
  1. Chunks dont law_short/article_num est vide, "?", ou incomplet.
  2. Découpage par article du CO et du CC (5 premiers + anomalies).
  3. Doublons exacts (même texte, IDs différents).

Usage :
    python audit_metadata.py
    python audit_metadata.py --examples 5      # nb d'exemples de texte affichés
    python audit_metadata.py --co 220 --cc 210 # forcer les SR du CO / CC
"""
from __future__ import annotations
import argparse
import hashlib
import re
from collections import Counter, defaultdict

from config import CHROMA_DIR, COLLECTION_NAME


# ── Détection du schéma de métadonnées ────────────────────────────────────────
# La base peut utiliser law_name/article_id (code actuel) OU law_short/article_num.
LAW_KEYS = ("law_short", "law_name")
ART_KEYS = ("article_num", "article_id")
SR_KEYS = ("law_sr", "law_short", "law_name")


def _pick_key(metas: list[dict], candidates: tuple[str, ...]) -> str | None:
    for key in candidates:
        if any(key in (m or {}) for m in metas):
            return key
    return None


def _is_suspect(value) -> tuple[bool, str]:
    """Retourne (suspect?, raison)."""
    if value is None:
        return True, "absent (None)"
    s = str(value).strip()
    if s == "":
        return True, "vide"
    if "?" in s:
        return True, "contient '?'"
    # Marqueurs de fallback connus du pipeline
    if s in ("complet", "GE-INCONNU", "Loi GE"):
        return True, f"fallback '{s}'"
    # "AFC-Circ-?" déjà couvert par le '?', mais on garde un filet incomplet :
    if s.endswith("-") or s.endswith("."):
        return True, "se termine par un séparateur (tronqué ?)"
    return False, ""


def _short(text: str, n: int = 200) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n] + " […]"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", type=int, default=5,
                    help="nombre d'exemples de texte à afficher par catégorie")
    ap.add_argument("--co", default="220", help="SR du Code des obligations")
    ap.add_argument("--cc", default="210", help="SR du Code civil")
    args = ap.parse_args()

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_collection(COLLECTION_NAME)

    total = col.count()
    print(f"Collection '{COLLECTION_NAME}' — {total} chunks\n")

    res = col.get(include=["documents", "metadatas"])
    ids = res.get("ids") or []
    docs = res.get("documents") or []
    metas = res.get("metadatas") or [{} for _ in ids]

    law_key = _pick_key(metas, LAW_KEYS) or "law_name"
    art_key = _pick_key(metas, ART_KEYS) or "article_id"
    sr_key = _pick_key(metas, SR_KEYS) or "law_sr"
    print(f"Champs détectés : law_short→'{law_key}', article_num→'{art_key}', "
          f"clé loi→'{sr_key}'\n")
    print("=" * 70)

    # ── Q1 : métadonnées suspectes ────────────────────────────────────────────
    print("\n### Q1 — law_short / article_num vides, '?', ou incomplets\n")
    suspects = []  # (id, raison_law, raison_art, law, art, sr, text)
    reason_counter = Counter()
    for i, _id in enumerate(ids):
        m = metas[i] or {}
        law = m.get(law_key)
        art = m.get(art_key)
        sr = m.get(sr_key)
        bad_law, why_law = _is_suspect(law)
        bad_art, why_art = _is_suspect(art)
        # On regarde aussi la clé loi (c'est là que vit "AFC-Circ-?")
        bad_sr, why_sr = _is_suspect(sr)
        if bad_law or bad_art or bad_sr:
            suspects.append((_id, law, art, sr, docs[i] if i < len(docs) else ""))
            if bad_law:
                reason_counter[f"{law_key} {why_law}"] += 1
            if bad_art:
                reason_counter[f"{art_key} {why_art}"] += 1
            if bad_sr:
                reason_counter[f"{sr_key} {why_sr}"] += 1

    print(f"TOTAL chunks suspects : {len(suspects)} / {total}\n")
    print("Répartition par raison :")
    for reason, n in reason_counter.most_common():
        print(f"  - {n:>5}  {reason}")

    print(f"\nExemples (jusqu'à {args.examples}) :")
    for _id, law, art, sr, text in suspects[: args.examples]:
        print(f"\n  ID       : {_id}")
        print(f"  {sr_key:9}: {sr!r}")
        print(f"  {law_key:9}: {law!r}")
        print(f"  {art_key:9}: {art!r}")
        print(f"  texte    : {_short(text)}")
    print("\n" + "=" * 70)

    # ── Q2 : découpage CO / CC ────────────────────────────────────────────────
    def audit_corpus(label: str, sr_value: str) -> None:
        print(f"\n### Q2 — {label} (SR {sr_value})\n")
        idx = [i for i in range(len(ids))
               if str((metas[i] or {}).get(sr_key)) == sr_value]
        if not idx:
            # Fallback : matcher sur law_name == label
            idx = [i for i in range(len(ids))
                   if str((metas[i] or {}).get(law_key)).upper() == label.upper()]
        print(f"  Chunks trouvés : {len(idx)}")
        if not idx:
            print(f"  ⚠ Aucun chunk pour SR={sr_value} ni {law_key}={label}. "
                  f"Vérifie la valeur réelle de {sr_key}.")
            return

        print("  5 premiers chunks :")
        for i in idx[:5]:
            m = metas[i] or {}
            print(f"    - {art_key}={m.get(art_key)!r:14} | "
                  f"{_short(docs[i] if i < len(docs) else '', 90)}")

        # Anomalies : article_id manquant / suspect
        art_vals = [(metas[i] or {}).get(art_key) for i in idx]
        missing = sum(1 for v in art_vals if _is_suspect(v)[0])
        print(f"\n  article_num manquant/suspect : {missing}")

        # Doublons de numéro d'article (signe de transitoires réutilisant la num.)
        dupe_arts = {a: n for a, n in Counter(
            str(v) for v in art_vals).items() if n > 1}
        if dupe_arts:
            top = sorted(dupe_arts.items(), key=lambda x: -x[1])[:10]
            print(f"  numéros d'article EN DOUBLE : {len(dupe_arts)} valeurs "
                  f"({sum(dupe_arts.values())} chunks concernés)")
            print("    top :", ", ".join(f"{a}×{n}" for a, n in top))
        else:
            print("  numéros d'article en double : 0 (1 chunk = 1 article ✓)")

        # Chunks couvrant plusieurs articles (heuristique sur le texte)
        multi = []
        for i in idx:
            t = docs[i] if i < len(docs) else ""
            # ≥2 occurrences de "Art. N" dans le corps → chunk multi-articles
            arts_in_text = re.findall(r"\bArt\.?\s+\d+", t)
            if len(arts_in_text) >= 2:
                multi.append((metas[i].get(art_key), len(arts_in_text)))
        if multi:
            print(f"  ⚠ chunks couvrant potentiellement plusieurs articles : "
                  f"{len(multi)} (ex. {multi[:5]})")

    audit_corpus("CO", args.co)
    audit_corpus("CC", args.cc)
    print("\n" + "=" * 70)

    # ── Q3 : doublons exacts ──────────────────────────────────────────────────
    print("\n### Q3 — doublons exacts (même texte, IDs différents)\n")
    by_hash: dict[str, list[int]] = defaultdict(list)
    for i, text in enumerate(docs):
        h = hashlib.sha1((text or "").encode("utf-8")).hexdigest()
        by_hash[h].append(i)

    dupe_groups = {h: g for h, g in by_hash.items() if len(g) > 1}
    extra = sum(len(g) - 1 for g in dupe_groups.values())
    print(f"  Groupes de texte identique : {len(dupe_groups)}")
    print(f"  Chunks en trop (doublons au-delà du 1er) : {extra}")

    if dupe_groups:
        print(f"\n  Exemples (jusqu'à {args.examples}) :")
        shown = 0
        for h, g in sorted(dupe_groups.items(), key=lambda x: -len(x[1])):
            if shown >= args.examples:
                break
            print(f"\n  ── {len(g)} copies identiques ──")
            for i in g:
                m = metas[i] or {}
                print(f"     ID={ids[i]}  {sr_key}={m.get(sr_key)!r} "
                      f"{art_key}={m.get(art_key)!r}")
            print(f"     texte : {_short(docs[g[0]])}")
            shown += 1
    print("\n" + "=" * 70)
    print("\nAudit terminé (aucune donnée modifiée).")


if __name__ == "__main__":
    main()
