import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import DocumentChunk
from src.core.vector_store import VectorStore

def test_vector_store():
    test_dir = Path(__file__).resolve().parent / "sample_data"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_db_dir = test_dir / "chroma_unit_test"
    if test_db_dir.exists():
        shutil.rmtree(test_db_dir)

    logs = []
    def log_cb(stage: str, msg: str, data: dict):
        logs.append((stage, msg))
        print(f"[{stage}] {msg}")

    # Use mock_mode=True for deterministic vector testing without API key
    store = VectorStore(
        persist_dir=test_db_dir,
        collection_name="test_knowledge",
        progress_callback=log_cb,
        mock_mode=True
    )

    chunks = [
        DocumentChunk(
            chunk_id="doc1_p1_c0",
            text="Enterprise data retention policy requires retaining financial documents for 7 years.",
            source_path="c:/data/doc1.pdf",
            filename="doc1.pdf",
            page_number=1,
            chunk_index=0,
            char_count=85
        ),
        DocumentChunk(
            chunk_id="doc1_p2_c1",
            text="Employee health insurance and retirement benefits are administered by HR Operations.",
            source_path="c:/data/doc1.pdf",
            filename="doc1.pdf",
            page_number=2,
            chunk_index=1,
            char_count=84
        ),
        DocumentChunk(
            chunk_id="doc2_p1_c0",
            text="Security access tokens expire every 24 hours and require biometric re-authentication.",
            source_path="c:/data/doc2.docx",
            filename="doc2.docx",
            page_number=1,
            chunk_index=0,
            char_count=84
        )
    ]

    # Add chunks
    indexed = store.add_chunks(chunks, batch_size=2)
    assert indexed == 3, f"Expected 3 indexed chunks, got {indexed}"

    # Verify stats
    stats = store.get_stats()
    assert stats["total_chunks"] == 3
    assert stats["total_documents"] == 2
    assert "doc1.pdf" in stats["documents"]
    assert "doc2.docx" in stats["documents"]

    # Test search
    results = store.similarity_search("financial retention policy", top_k=2)
    assert len(results) == 2
    top = results[0]
    assert top.chunk.chunk_id in ["doc1_p1_c0", "doc1_p2_c1", "doc2_p1_c0"]
    assert 0.0 <= top.similarity_score <= 1.0

    # Verify persistence: create new instance pointing to same dir
    store_reloaded = VectorStore(
        persist_dir=test_db_dir,
        collection_name="test_knowledge",
        mock_mode=True
    )
    stats_reloaded = store_reloaded.get_stats()
    assert stats_reloaded["total_chunks"] == 3

    # Verify no emojis in logs
    for stage, msg in logs:
        for ch in msg:
            assert ord(ch) < 10000, f"Emoji found in log: {msg}"

    print("\nALL_VECTOR_STORE_TESTS_PASSED_SUCCESSFULLY")

if __name__ == "__main__":
    test_vector_store()
