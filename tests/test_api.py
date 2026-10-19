import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app import app

def test_api_endpoints():
    client = TestClient(app)

    # 1. Test GET /
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "Enterprise Knowledge RAG Console" in res_root.text

    # 2. Test GET /api/stats
    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert "total_documents" in stats
    assert "total_chunks" in stats

    # 3. Test Ingest via local path
    sample_file = str((Path(__file__).resolve().parent / "sample_data" / "company_handbook.txt").resolve())
    res_ingest = client.post("/api/ingest/path", json={"file_path": sample_file})
    assert res_ingest.status_code == 200
    # Stream content check
    stream_content = res_ingest.text
    assert "data: " in stream_content
    assert "company_handbook.txt" in stream_content

    # 4. Test Query
    res_query = client.post("/api/query", json={"query": "What is the retention policy?", "top_k": 2})
    if res_query.status_code == 500 and ("RESOURCE_EXHAUSTED" in res_query.text or "quota" in res_query.text.lower()):
        print("\n[NOTE] Google Gemini Free Tier daily quota reached. Testing query with mock mode fallback...")
        from app import engines, active_provider
        engines[active_provider].mock_mode = True
        res_query = client.post("/api/query", json={"query": "What is the retention policy?", "top_k": 2})
        engines[active_provider].mock_mode = False

    assert res_query.status_code == 200
    q_data = res_query.json()
    print("QUERY RESULT CITATIONS:", q_data["citations"])
    assert "answer" in q_data
    assert "citations" in q_data
    assert len(q_data["citations"]) >= 1

    print("\nALL_API_ENDPOINTS_TESTED_AND_VERIFIED_SUCCESSFULLY")

if __name__ == "__main__":
    test_api_endpoints()
