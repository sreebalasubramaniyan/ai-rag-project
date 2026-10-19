import os
import json
import shutil
import time
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment
load_dotenv()

from src.core.rag_engine import RAGEngine
from src.core.ollama_client import OllamaClient
from src.core.openrouter_client import OpenRouterClient

# Paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = DATA_DIR / "chroma_db"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# API Key Validation
api_key = os.getenv("GEMINI_API_KEY", "").strip()
mock_mode = False
if not api_key or api_key == "your_gemini_api_key_here" or api_key.startswith("your_"):
    mock_mode = True

# Initialize Clients & Engines for Multi-Provider Support (Gemini, Ollama, OpenRouter)
ollama_client = OllamaClient()
openrouter_client = OpenRouterClient()

engines = {
    "gemini": RAGEngine(
        persist_dir=str(CHROMA_DIR),
        provider="gemini",
        mock_mode=mock_mode
    ),
    "ollama": RAGEngine(
        persist_dir=str(CHROMA_DIR),
        provider="ollama",
        mock_mode=False
    ),
    "openrouter": RAGEngine(
        persist_dir=str(CHROMA_DIR),
        provider="openrouter",
        mock_mode=False
    )
}

active_provider = os.getenv("DEFAULT_PROVIDER", "gemini").lower()
if active_provider not in engines:
    active_provider = "gemini"

def get_rag_engine() -> RAGEngine:
    return engines.get(active_provider, engines["gemini"])

app = FastAPI(
    title="Dual-Stage Privacy Enforcement for Fully Offline Enterprise RAG",
    description="Query-Adaptive Privacy-Preserving Offline RAG System with Context Filtering and Output Leakage Prevention",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestPathRequest(BaseModel):
    file_path: str

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 4
    enforce_privacy: Optional[bool] = True

class ProviderSwitchRequest(BaseModel):
    provider: str
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None

@app.get("/api/providers")
async def get_providers():
    """Returns status and configuration of available AI providers (Gemini, Ollama, OpenRouter)."""
    ollama_ok = ollama_client.is_available()
    installed_models = ollama_client.list_models() if ollama_ok else []
    openrouter_ok = openrouter_client.is_available()

    return {
        "active_provider": active_provider,
        "providers": {
            "openrouter": {
                "name": "OpenRouter (Free Online)",
                "available": openrouter_ok,
                "chat_model": engines["openrouter"].chat_model,
                "embed_model": engines["openrouter"].vector_store.embed_model,
                "collection_name": engines["openrouter"].vector_store.collection_name,
                "free_models": openrouter_client.FREE_FALLBACK_MODELS,
                "privacy": "Cloud API (Free Open-Source Models)",
                "is_active": active_provider == "openrouter"
            },
            "gemini": {
                "name": "Google Gemini (Cloud)",
                "available": bool(api_key and not mock_mode),
                "chat_model": engines["gemini"].chat_model,
                "embed_model": engines["gemini"].vector_store.embed_model,
                "collection_name": engines["gemini"].vector_store.collection_name,
                "privacy": "Cloud API (Encrypted in transit)",
                "is_active": active_provider == "gemini"
            },
            "ollama": {
                "name": "Ollama (Local Offline)",
                "available": ollama_ok,
                "base_url": ollama_client.base_url,
                "chat_model": engines["ollama"].chat_model,
                "embed_model": engines["ollama"].vector_store.embed_model,
                "collection_name": engines["ollama"].vector_store.collection_name,
                "installed_models": installed_models,
                "privacy": "100% Offline (Zero Cloud Egress)",
                "is_active": active_provider == "ollama"
            }
        }
    }

@app.post("/api/provider/switch")
async def switch_provider(req: ProviderSwitchRequest):
    """Switches the active provider between OpenRouter, Gemini, and Local Offline (Ollama)."""
    global active_provider
    target = req.provider.lower().strip()
    if target not in ["gemini", "ollama", "openrouter"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider: '{target}'. Supported options: 'openrouter', 'gemini', 'ollama'."
        )

    active_provider = target
    current_engine = get_rag_engine()
    if req.chat_model:
        current_engine.chat_model = req.chat_model
    if req.embed_model:
        current_engine.vector_store.embed_model = req.embed_model

    privacy_label = "100% Offline & Private" if active_provider == "ollama" else (
        "OpenRouter Free Online (Llama 3.3 70B)" if active_provider == "openrouter" else "Cloud (Google Gemini)"
    )

    return {
        "status": "success",
        "active_provider": active_provider,
        "chat_model": current_engine.chat_model,
        "embed_model": current_engine.vector_store.embed_model,
        "collection_name": current_engine.vector_store.collection_name,
        "privacy_mode": privacy_label
    }

@app.get("/api/stats")
async def get_stats():
    """Returns knowledge base stats and active model configuration."""
    current_engine = get_rag_engine()
    stats = current_engine.get_stats()
    stats["active_provider"] = active_provider
    stats["mock_mode"] = current_engine.mock_mode
    stats["privacy_mode"] = "100% Offline & Private" if active_provider == "ollama" else (
        "OpenRouter Free Online" if active_provider == "openrouter" else "Cloud (Google Gemini)"
    )
    stats["ollama_connected"] = ollama_client.is_available()
    stats["openrouter_connected"] = openrouter_client.is_available()
    return stats

@app.post("/api/clear")
async def clear_database():
    """Clears all vectorized documents from the active provider's ChromaDB collection."""
    current_engine = get_rag_engine()
    current_engine.clear()
    return {
        "status": "success",
        "message": f"Knowledge base collection '{current_engine.vector_store.collection_name}' cleared."
    }

@app.post("/api/ingest/upload")
async def ingest_uploaded_file(file: UploadFile = File(...)):
    """Uploads a file and streams real-time technical pipeline progress via SSE."""
    original_name = file.filename or "uploaded_document"
    destination_path = UPLOADS_DIR / original_name

    # Save uploaded file
    with open(destination_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return StreamingResponse(
        _stream_ingestion(str(destination_path)),
        media_type="text/event-stream"
    )

@app.post("/api/ingest/path")
async def ingest_local_path(req: IngestPathRequest):
    """Ingests a file from a local filesystem path and streams technical pipeline progress via SSE."""
    file_path = req.file_path.strip().strip('"').strip("'")
    target = Path(file_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found on system: {file_path}")

    return StreamingResponse(
        _stream_ingestion(str(target)),
        media_type="text/event-stream"
    )

async def _stream_ingestion(file_path: str) -> AsyncGenerator[str, None]:
    """Generator yielding technical telemetry events during document ingestion."""
    event_queue = asyncio.Queue()
    current_engine = get_rag_engine()

    def progress_handler(stage: str, message: str, data: dict):
        event_queue.put_nowait({
            "type": "progress",
            "stage": stage,
            "message": message,
            "data": data,
            "timestamp": time.strftime("%H:%M:%S")
        })

    # Run ingestion in worker thread
    async def run_worker():
        try:
            old_cb = current_engine.loader.progress_callback
            current_engine.loader.progress_callback = progress_handler
            current_engine.chunker.progress_callback = progress_handler
            current_engine.vector_store.progress_callback = progress_handler

            res = await asyncio.to_thread(current_engine.ingest_file, file_path)
            await event_queue.put({
                "type": "result",
                "result": res,
                "timestamp": time.strftime("%H:%M:%S")
            })
        except Exception as exc:
            await event_queue.put({
                "type": "error",
                "error": str(exc),
                "timestamp": time.strftime("%H:%M:%S")
            })
        finally:
            await event_queue.put(None)  # Sentinel to end stream

    asyncio.create_task(run_worker())

    while True:
        event = await event_queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event)}\n\n"

@app.post("/api/query")
async def execute_query(req: QueryRequest):
    """Executes vector retrieval, context evaluation, and grounded synthesis with citation metadata."""
    query_str = req.query.strip()
    if not query_str:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    current_engine = get_rag_engine()
    events = []
    def progress_handler(stage: str, message: str, data: dict):
        events.append({
            "stage": stage,
            "message": message,
            "data": data,
            "timestamp": time.strftime("%H:%M:%S")
        })

    old_cb = current_engine.vector_store.progress_callback
    current_engine.vector_store.progress_callback = progress_handler
    current_engine.progress_callback = progress_handler

    try:
        response = await asyncio.to_thread(
            current_engine.query,
            query_str,
            req.top_k or 4,
            True if req.enforce_privacy is None else req.enforce_privacy
        )
    except ConnectionError as conn_err:
        raise HTTPException(status_code=503, detail=str(conn_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        current_engine.vector_store.progress_callback = old_cb
        current_engine.progress_callback = None

    # Format citations
    citations_data = []
    for c in response.citations:
        citations_data.append({
            "citation_id": c.citation_id,
            "source_filename": c.source_filename,
            "source_path": c.source_path,
            "page_number": c.page_number,
            "chunk_id": c.chunk_id,
            "similarity_score": c.similarity_score,
            "relevance_percent": round(c.similarity_score * 100, 1),
            "excerpt": c.excerpt
        })

    return {
        "query": response.query,
        "answer": response.answer,
        "is_restricted": response.is_restricted,
        "restriction_category": response.restriction_category,
        "citations": citations_data,
        "total_chunks_evaluated": response.total_chunks_evaluated,
        "processing_time_ms": response.processing_time_ms,
        "privacy_audit": response.privacy_audit,
        "telemetry_events": events
    }

@app.get("/api/privacy/policy")
async def get_privacy_policy():
    """Returns dual-stage privacy enforcement specifications and air-gapped guarantees."""
    return {
        "title": "Dual-Stage Privacy Enforcement Architecture",
        "patent_specification": "Query-Adaptive Privacy-Preserving Offline RAG System with Context Filtering and Output Leakage Prevention",
        "active_provider": active_provider,
        "offline_guarantee": "100% Air-Gapped (Zero Cloud Egress)" if active_provider == "ollama" else "Cloud Hybrid Mode",
        "stage_1_context_filtering": {
            "name": "Stage 1: Query-Adaptive Context Filter (Pre-Generation)",
            "description": "Evaluates candidate chunks against user clearance and adaptively sanitizes PII before prompt compilation.",
            "clearance_levels": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
        },
        "stage_2_output_leakage_prevention": {
            "name": "Stage 2: Output Leakage Prevention Engine (Post-Generation)",
            "description": "Verifies synthesized answers against unauthorized entity leakage and intercepts sensitive data prior to delivery.",
            "guarantee": "Zero-Leakage Cryptographic & Policy Compliance Audit"
        }
    }

# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h3>Enterprise RAG UI loading...</h3>")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"[STARTUP] Starting Enterprise RAG Server at http://{host}:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=True)
