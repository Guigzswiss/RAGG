"""
Serveur OpenAI-compatible pour Open WebUI.

Expose le pipeline RAG (ChromaDB + BM25 + Infomaniak) derrière une API
/v1/chat/completions que Open WebUI (ou tout client OpenAI) peut appeler.

Usage :
    pip install fastapi uvicorn
    python server.py                  # lance sur http://localhost:8000
    python server.py --port 9000      # port custom

Puis dans Open WebUI :
    Settings → Connections → OpenAI API
    URL  : http://localhost:8000/v1
    Key  : any-value-works
"""
from __future__ import annotations
import argparse
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import json


_engine = None
_model_name = None


def _init_rag():
    global _engine, _model_name
    from config import (
        INFOMANIAK_TOKEN, INFOMANIAK_BASE_URL,
        MODEL_EMBED, MODEL_CHAT,
        CHROMA_DIR, COLLECTION_NAME,
    )
    from embedder import InfomaniakEmbedder
    from index import HybridIndex
    from query import RAGEngine
    from openai import OpenAI

    print("Initialisation du pipeline RAG...")
    embedder = InfomaniakEmbedder(INFOMANIAK_BASE_URL, INFOMANIAK_TOKEN, MODEL_EMBED)
    idx = HybridIndex(embedder, CHROMA_DIR, COLLECTION_NAME)
    print(f"  Index chargé : {idx.count()} chunks")

    chat_client = OpenAI(api_key=INFOMANIAK_TOKEN, base_url=INFOMANIAK_BASE_URL)
    _engine = RAGEngine(idx, chat_client, MODEL_CHAT)
    _model_name = f"rag-{MODEL_CHAT}"
    print(f"  Modèle : {MODEL_CHAT}")
    print("  Prêt.\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_rag()
    yield


app = FastAPI(title="Swiss Law RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": _model_name or "rag-swiss-law",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local-rag",
            }
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    question = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            question = msg.get("content", "")
            break

    if not question:
        return _error("Aucune question trouvée dans les messages.")

    from config import TOP_K_FINAL
    result = _engine.ask(question, top_k=TOP_K_FINAL)

    answer = result["answer"]
    if result["sources"]:
        answer += "\n\n---\n**Sources :**\n"
        for s in result["sources"]:
            law = s.get("law", "?")
            art = s.get("article", "?")
            url = s.get("url", "")
            if url:
                answer += f"- [{law}, {art}]({url})\n"
            else:
                answer += f"- {law}, {art}\n"

    if stream:
        return StreamingResponse(
            _stream_response(answer),
            media_type="text/event-stream",
        )

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": _model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _stream_response(text: str):
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    words = text.split(" ")
    for i, word in enumerate(words):
        token = word if i == 0 else " " + word
        chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": _model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    final = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": _model_name,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


def _error(msg: str):
    return {"error": {"message": msg, "type": "invalid_request_error"}}


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
