import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.ollama_client import OllamaClient
from src.core.vector_store import VectorStore
from src.core.rag_engine import RAGEngine
from src.core.models import DocumentChunk
from fastapi.testclient import TestClient
from app import app

def test_ollama_client():
    client = OllamaClient(base_url="http://localhost:11434")
    # Ping should return a boolean (True if running, False if not)
    is_running = client.is_available()
    assert isinstance(is_running, bool)

    # Models list should return a list
    models = client.list_models()
    assert isinstance(models, list)
    print(f"Ollama running: {is_running}, installed models: {models}")

def test_vector_store_dual_provider():
    # Test Ollama vector store in mock mode
    vs_ollama = VectorStore(
        persist_dir="./data/test_chroma_ollama",
        provider="ollama",
        mock_mode=True
    )
    assert vs_ollama.provider == "ollama"
    assert "ollama" in vs_ollama.collection_name
    assert "nomic_embed_text" in vs_ollama.collection_name

    # Add mock chunks
    chunk = DocumentChunk(
        chunk_id="test_chunk_1",
        text="Confidential financial audit data for internal review only.",
        page_number=1,
        source_path="internal_doc.pdf",
        filename="internal_doc.pdf",
        chunk_index=0,
        char_count=60
    )
    indexed = vs_ollama.add_chunks([chunk])
    assert indexed == 1

    stats = vs_ollama.get_stats()
    assert stats["provider"] == "ollama"
    assert stats["total_chunks"] >= 1

    # Cleanup
    vs_ollama.clear()

def test_rag_engine_ollama():
    engine = RAGEngine(
        persist_dir="./data/test_chroma_rag_ollama",
        provider="ollama",
        mock_mode=True
    )
    assert engine.provider == "ollama"
    assert engine.chat_model == "llama3.2"

    res = engine.query("What is the financial audit policy?")
    assert res.query == "What is the financial audit policy?"
    print("OLLAMA_RAG_SYNTHESIS_ANSWER:", res.answer)
    engine.clear()

def test_api_provider_switching():
    client = TestClient(app)

    # 1. Test GET /api/providers
    res_providers = client.get("/api/providers")
    assert res_providers.status_code == 200
    p_data = res_providers.json()
    assert "active_provider" in p_data
    assert "gemini" in p_data["providers"]
    assert "ollama" in p_data["providers"]

    # 2. Test Switch to Ollama
    res_switch = client.post("/api/provider/switch", json={"provider": "ollama"})
    assert res_switch.status_code == 200
    switch_data = res_switch.json()
    assert switch_data["active_provider"] == "ollama"
    assert "ollama" in switch_data["collection_name"]
    assert "100% Offline" in switch_data["privacy_mode"]

    # 3. Test GET /api/stats reflecting active provider
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    stats_data = res_stats.json()
    assert stats_data["active_provider"] == "ollama"

    # 4. Switch back to Gemini
    res_switch_back = client.post("/api/provider/switch", json={"provider": "gemini"})
    assert res_switch_back.status_code == 200
    assert res_switch_back.json()["active_provider"] == "gemini"

    print("\nALL_OLLAMA_AND_DUAL_PROVIDER_TESTS_PASSED_SUCCESSFULLY")

if __name__ == "__main__":
    test_ollama_client()
    test_vector_store_dual_provider()
    test_rag_engine_ollama()
    test_api_provider_switching()
