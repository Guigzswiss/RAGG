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
