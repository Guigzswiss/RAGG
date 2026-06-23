"""
CLI principal pour le pipeline RAG juridique suisse.

Commandes :
  python run.py selftest          — test hors-ligne (aucun appel réseau)
  python run.py testinfomaniak    — test avec l'API Infomaniak réelle
  python run.py index <SR> ...    — indexer une loi depuis Fedlex
  python run.py ask "<question>"  — poser une question
"""
from __future__ import annotations
import sys
import os


def _make_index(embedder, offline: bool = False):
    """Crée l'index hybride avec le bon chemin de données."""
    from config import CHROMA_DIR, COLLECTION_NAME
    from index import HybridIndex
    import tempfile

    chroma_dir = tempfile.mkdtemp(prefix="chroma_test_") if offline else CHROMA_DIR
    os.makedirs(chroma_dir, exist_ok=True)
    return HybridIndex(embedder, chroma_dir, COLLECTION_NAME)


def cmd_selftest():
    """Test hors-ligne : embedder local + ChromaDB éphémère."""
    print("=== SELFTEST (hors-ligne) ===")

    from embedder import LocalEmbedder
    from fedlex import load_sample_lifd
    from query import RAGEngine, build_context

    embedder = LocalEmbedder()
    idx = _make_index(embedder, offline=True)

    chunks = load_sample_lifd()
    idx.add_chunks(chunks)
    print(f"  {len(chunks)} articles indexés (ChromaDB local éphémère)")

    results = idx.search("Qui est assujetti à l'impôt sur le revenu?", top_k_final=3)
    print(f"  {len(results)} résultat(s) de recherche hybride")

    if results:
        meta = results[0]["metadata"]
        print(f"  Meilleur résultat : {meta.get('law_name')}, {meta.get('article_id')}")
        print()
        print("Contexte construit :")
        print(build_context(results[:2]))
    else:
        print("  ATTENTION : aucun résultat — vérifie ChromaDB.")

    print()
    print("=== SELFTEST PASSED ===")


def cmd_testinfomaniak():
    """Test avec l'API Infomaniak : embeddings réels + génération réelle."""
    print("=== TEST INFOMANIAK ===")

    try:
        from config import INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL, MODEL_EMBED, MODEL_CHAT
        print(f"  Token chargé depuis token.txt : {INFOMANIAK_TOKEN[:8]}...{INFOMANIAK_TOKEN[-4:]}")
        print(f"  Base URL : {INFOMANIAK_BASE_URL}")
        print(f"  Modèle embed : {MODEL_EMBED}")
        print(f"  Modèle chat  : {MODEL_CHAT}")
    except Exception as e:
        print(f"  ERREUR config : {e}")
        sys.exit(1)

    from embedder import InfomaniakEmbedder
    from fedlex import load_sample_lifd
    from query import RAGEngine
    from openai import OpenAI

    print("\n  Initialisation de l'embedder Infomaniak...")
    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)

    print("  Indexation de l'échantillon LIFD...")
    idx = _make_index(embedder, offline=True)
    chunks = load_sample_lifd()
    idx.add_chunks(chunks)
    print(f"  {len(chunks)} articles indexés avec embeddings Infomaniak")

    print("\n  Création du client de génération...")
    chat_client = OpenAI(api_key=INFOMANIAK_TOKEN, base_url=INFOMANIAK_BASE_URL)
    engine = RAGEngine(idx, chat_client, MODEL_CHAT)

    question = "Qui est assujetti à l'impôt fédéral direct sur le revenu en Suisse?"
    print(f"\n  Question : {question}")
    print("  Génération de la réponse...\n")

    result = engine.ask(question)

    print("=" * 60)
    print("RÉPONSE :")
    print(result["answer"])
    print()
    print("SOURCES CITÉES :")
    for s in result["sources"]:
        print(f"  - {s['law']}, {s['article']} : {s['url']}")
    print("=" * 60)
    print("\n=== TEST INFOMANIAK PASSED ===")


def cmd_index(sr_list: list[str]):
    """Indexe une ou plusieurs lois depuis Fedlex."""
    from config import INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL, MODEL_EMBED
    from embedder import InfomaniakEmbedder
    from fedlex import fetch_law_from_fedlex

    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)
    idx = _make_index(embedder, offline=False)

    for sr in sr_list:
        print(f"\nIndexation de SR {sr}...")
        try:
            chunks = fetch_law_from_fedlex(sr)
            idx.add_chunks(chunks)
            print(f"  {len(chunks)} articles indexés pour SR {sr}")
        except Exception as e:
            print(f"  ERREUR pour SR {sr} : {e}")


def cmd_index_pdf(folder: str):
    """Indexe tous les PDFs de lois cantonales dans un dossier."""
    from config import INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL, MODEL_EMBED
    from embedder import InfomaniakEmbedder
    from parse_pdf_ge import parse_pdf_folder

    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)
    idx = _make_index(embedder, offline=False)

    print(f"\nParsing des PDFs dans : {folder}")
    all_chunks = parse_pdf_folder(folder)

    total = 0
    for filename, chunks in all_chunks.items():
        if not chunks:
            continue
        print(f"\nIndexation de {filename}...")
        idx.add_chunks(chunks)
        print(f"  {len(chunks)} articles indexés")
        total += len(chunks)

    print(f"\nTotal : {total} articles indexés depuis {len(all_chunks)} PDF(s)")


def cmd_index_ge(refs: list[str]):
    """Indexe des lois cantonales genevoises depuis ge.ch/legi."""
    from config import INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL, MODEL_EMBED
    from embedder import InfomaniakEmbedder
    from canton_ge import fetch_law_from_ge, LOIS_GE

    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)
    idx = _make_index(embedder, offline=False)

    # Si "all" → indexer toutes les lois connues
    if refs == ["all"]:
        refs = list(LOIS_GE.keys())

    for ref in refs:
        print(f"\nIndexation GE : {ref}...")
        try:
            chunks = fetch_law_from_ge(ref)
            if not chunks:
                print(f"  ATTENTION : aucun article extrait pour {ref}")
                continue
            idx.add_chunks(chunks)
            print(f"  {len(chunks)} articles indexés pour {ref}")
        except Exception as e:
            print(f"  ERREUR pour {ref} : {e}")


def cmd_reset():
    """Vide complètement la collection ChromaDB (pour re-indexer proprement)."""
    from config import CHROMA_DIR, COLLECTION_NAME
    import chromadb

    print(f"Suppression de la collection '{COLLECTION_NAME}' dans {CHROMA_DIR}...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
        print("  Collection supprimée.")
    except Exception as e:
        print(f"  Rien à supprimer ou erreur : {e}")
    print("  Prêt. Re-indexe avec : python run.py index <SR> / index-pdf <dossier>")


def cmd_cleanup(law_sr: str = "GE-INCONNU"):
    """Supprime les entrées d'une loi spécifique (par défaut GE-INCONNU) sans toucher au reste."""
    from config import CHROMA_DIR, COLLECTION_NAME
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        print("Collection introuvable.")
        return

    before = col.count()
    col.delete(where={"law_sr": {"$eq": law_sr}})
    after = col.count()
    removed = before - after
    if removed == 0:
        print(f"  Aucune entrée avec law_sr='{law_sr}' trouvée.")
    else:
        print(f"  Supprimé : {removed} entrées. Total restant : {after} chunks.")


def cmd_cleanup_circ():
    """Supprime toutes les circulaires AFC (law_sr commençant par 'AFC-Circ').

    À lancer avant de ré-indexer les circulaires : comme la correction du
    parsing change le law_sr (AFC-Circ-? → AFC-Circ-155), un simple
    index-pdf ajouterait les nouveaux chunks à côté des anciens au lieu de
    les remplacer. On efface donc d'abord tout le bloc AFC-Circ-*.
    """
    from config import CHROMA_DIR, COLLECTION_NAME
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        print("Collection introuvable.")
        return

    before = col.count()
    res = col.get(include=["metadatas"])
    ids = res.get("ids") or []
    metas = res.get("metadatas") or []
    to_delete = [
        ids[i] for i in range(len(ids))
        if str((metas[i] or {}).get("law_sr", "")).startswith("AFC-Circ")
    ]
    if not to_delete:
        print("  Aucune circulaire AFC trouvée (law_sr 'AFC-Circ*').")
        return

    BATCH = 500
    for start in range(0, len(to_delete), BATCH):
        col.delete(ids=to_delete[start : start + BATCH])

    after = col.count()
    print(f"  Supprimé : {before - after} chunks de circulaires AFC. "
          f"Total restant : {after} chunks.")
    print("  Ré-indexe avec : python run.py index-pdf <dossier_des_circulaires>")


def cmd_reindex_ge():
    """Re-indexe proprement TOUTES les lois cantonales genevoises (catégorie D).

    1. Supprime tous les chunks dont law_sr commence par 'D ' (issus des PDF
       SILGENEVE : multi-lois mal classées + versions périmées).
    2. Ré-indexe chaque loi depuis ge.ch/legi (version actuelle, bonne réf).

    Les lois fédérales, vaudoises, circulaires AFC et LRCV ne sont PAS touchées.
    """
    from config import (INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL, MODEL_EMBED,
                        CHROMA_DIR, COLLECTION_NAME)
    from embedder import InfomaniakEmbedder
    from canton_ge import fetch_law_from_ge, LOIS_GE
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        col = client.get_collection(COLLECTION_NAME)
    except Exception:
        print("Collection introuvable.")
        return

    before = col.count()
    print(f"Collection : {before} chunks au total.\n")

    # 1. Recenser les chunks Genève (law_sr commençant par 'D ')
    res = col.get(include=["metadatas"])
    ids = res.get("ids") or []
    metas = res.get("metadatas") or []
    ge_ids = []
    by_law: dict[str, int] = {}
    for i, _id in enumerate(ids):
        sr = str((metas[i] or {}).get("law_sr", ""))
        if sr.startswith("D "):
            ge_ids.append(_id)
            by_law[sr] = by_law.get(sr, 0) + 1

    print("Chunks Genève actuels (à supprimer) :")
    for sr, n in sorted(by_law.items()):
        print(f"  {sr:10s} : {n}")
    print(f"  TOTAL    : {len(ge_ids)}\n")

    # 2. Supprimer par lots
    if ge_ids:
        BATCH = 500
        for s in range(0, len(ge_ids), BATCH):
            col.delete(ids=ge_ids[s : s + BATCH])
        print(f"Supprimé : {len(ge_ids)} chunks. Collection : {col.count()} chunks.\n")

    # 3. Ré-indexer chaque loi depuis ge.ch/legi
    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)
    from index import HybridIndex
    idx = HybridIndex(embedder, CHROMA_DIR, COLLECTION_NAME)

    total_added = 0
    for ref, name in LOIS_GE.items():
        print(f"\n=== {ref} ({name}) ===")
        try:
            chunks = fetch_law_from_ge(ref, name)
            if not chunks:
                print(f"  ATTENTION : 0 article pour {ref}, ignoré.")
                continue
            idx.add_chunks(chunks)
            total_added += len(chunks)
            print(f"  {len(chunks)} articles indexés.")
        except Exception as e:
            print(f"  ERREUR pour {ref} : {e}")

    after = idx.count()
    print(f"\n{'=' * 50}")
    print(f"Re-index terminé.")
    print(f"  Avant : {before} chunks")
    print(f"  Après : {after} chunks  (+{total_added} articles GE propres)")


def cmd_ask(question: str):
    """Pose une question au moteur RAG."""
    from config import INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL, MODEL_EMBED, MODEL_CHAT, TOP_K_FINAL
    from embedder import InfomaniakEmbedder
    from query import RAGEngine
    from openai import OpenAI
    import os

    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)
    idx = _make_index(embedder, offline=False)

    if idx.count() == 0:
        print("L'index est vide. Lance d'abord : python run.py index 642.11")
        sys.exit(1)

    chat_client = OpenAI(api_key=INFOMANIAK_TOKEN, base_url=INFOMANIAK_BASE_URL)
    engine = RAGEngine(idx, chat_client, MODEL_CHAT)

    result = engine.ask(question, top_k=TOP_K_FINAL)
    print("\n" + "=" * 60)
    print("RÉPONSE :")
    print(result["answer"])
    print()
    print("SOURCES :")
    for s in result["sources"]:
        print(f"  - {s['law']}, {s['article']} : {s['url']}")
    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "selftest":
        cmd_selftest()
    elif cmd == "testinfomaniak":
        cmd_testinfomaniak()
    elif cmd == "index":
        if len(sys.argv) < 3:
            print("Usage : python run.py index <SR> [SR2 ...]")
            sys.exit(1)
        cmd_index(sys.argv[2:])
    elif cmd == "index-pdf":
        if len(sys.argv) < 3:
            print("Usage : python run.py index-pdf <dossier>")
            sys.exit(1)
        cmd_index_pdf(sys.argv[2])
    elif cmd == "index-ge":
        if len(sys.argv) < 3:
            print("Usage : python run.py index-ge <ref> [ref2 ...]  ou  index-ge all")
            sys.exit(1)
        cmd_index_ge(sys.argv[2:])
    elif cmd == "reset":
        cmd_reset()
    elif cmd == "cleanup":
        law_sr = sys.argv[2] if len(sys.argv) > 2 else "GE-INCONNU"
        cmd_cleanup(law_sr)
    elif cmd == "cleanup-circ":
        cmd_cleanup_circ()
    elif cmd == "reindex-ge":
        cmd_reindex_ge()
    elif cmd == "ask":
        if len(sys.argv) < 3:
            print('Usage : python run.py ask "<question>"')
            sys.exit(1)
        cmd_ask(sys.argv[2])
    else:
        print(f"Commande inconnue : {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
