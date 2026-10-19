import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.rag_engine import RAGEngine

def test_rag_engine_end_to_end():
    # Base all test paths relative to this test file's directory
    test_dir = Path(__file__).resolve().parent / "sample_data"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_db_dir = test_dir / "chroma_rag_engine_test"

    if test_db_dir.exists():
        shutil.rmtree(test_db_dir)

    logs = []
    def log_cb(stage: str, msg: str, data: dict):
        logs.append((stage, msg))
        print(f"[{stage}] {msg}")

    engine = RAGEngine(
        persist_dir=str(test_db_dir),
        progress_callback=log_cb,
        mock_mode=True
    )

    # 1. Create or ensure sample file exists
    sample_file = test_dir / "company_handbook.txt"
    if not sample_file.exists():
        sample_file.write_text(
            "ACME ENTERPRISE KNOWLEDGE POLICY\n\n"
            "Section 1: Data Retention\n"
            "All customer records must be retained for exactly seven years following contract completion. "
            "Records older than seven years must be permanently expunged according to corporate compliance guidelines.\n\n"
            "Section 2: Security Protocols\n"
            "Multi-factor authentication (MFA) is mandatory for all employee access to enterprise databases. "
            "Any hardware token loss must be reported to the IT Security Desk within two hours.",
            encoding="utf-8"
        )

    # Ingest document using absolute path
    ingest_result = engine.ingest_file(str(sample_file))

    assert ingest_result["filename"] == "company_handbook.txt"
    assert ingest_result["chunks_indexed"] >= 1
    assert ingest_result["total_pages"] >= 1

    # 2. Check stats
    stats = engine.get_stats()
    assert stats["total_documents"] == 1
    assert "company_handbook.txt" in stats["documents"]

    # 3. Query the knowledge base
    query_text = "What is the data retention policy?"
    response = engine.query(query_text, top_k=2)

    assert response.query == query_text
    assert len(response.answer) > 0
    assert len(response.citations) >= 1

    citation = response.citations[0]
    assert citation.source_filename == "company_handbook.txt"
    assert citation.page_number == 1
    assert len(citation.excerpt) > 0
    assert 0.0 <= citation.similarity_score <= 1.0

    # 4. Verify no emojis in telemetry logs
    for stage, msg in logs:
        for ch in msg:
            assert ord(ch) < 10000, f"Emoji or non-ascii decorative character found in log: {msg}"

    print("\nALL_RAG_ENGINE_TESTS_PASSED_SUCCESSFULLY")

if __name__ == "__main__":
    test_rag_engine_end_to_end()
