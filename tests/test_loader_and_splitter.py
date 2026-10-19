import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypdf import PdfWriter
from src.core.loader import DocumentLoader
from src.core.splitter import SemanticChunker

def test_loader_and_splitter():
    test_dir = Path(__file__).resolve().parent / "sample_data"
    test_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create a sample text document
    sample_txt = test_dir / "company_handbook.txt"
    sample_txt.write_text(
        "ACME ENTERPRISE KNOWLEDGE POLICY\n\n"
        "Section 1: Data Retention\n"
        "All customer records must be retained for exactly seven years following contract completion. "
        "Records older than seven years must be permanently expunged according to corporate compliance guidelines.\n\n"
        "Section 2: Security Protocols\n"
        "Multi-factor authentication (MFA) is mandatory for all employee access to enterprise databases. "
        "Any hardware token loss must be reported to the IT Security Desk within two hours.",
        encoding="utf-8"
    )

    # 2. Create a sample CSV
    sample_csv = test_dir / "q3_financials.csv"
    sample_csv.write_text(
        "Department,Budget_Allocated,Spend_Q3,Variance\n"
        "Engineering,1500000,1420000,80000\n"
        "Marketing,850000,910000,-60000\n"
        "Operations,420000,390000,30000",
        encoding="utf-8"
    )

    # 3. Create a multi-page PDF
    sample_pdf = test_dir / "project_charter.pdf"
    writer = PdfWriter()
    # Create page 1 with blank page and add annotations / or add blank page with text stream
    # pypdf allows creating blank page and we can write metadata or test page extraction
    page1 = writer.add_blank_page(width=612, height=792)
    page2 = writer.add_blank_page(width=612, height=792)
    with open(sample_pdf, "wb") as f:
        writer.write(f)

    # Test callback collection
    logs = []
    def log_cb(stage: str, msg: str, data: dict):
        logs.append((stage, msg))
        print(f"[{stage}] {msg}")

    loader = DocumentLoader(progress_callback=log_cb)
    chunker = SemanticChunker(chunk_size=300, chunk_overlap=50, progress_callback=log_cb)

    # Test TXT Loading & Chunking
    txt_doc = loader.load(str(sample_txt))
    assert txt_doc.total_pages == 1, f"Expected 1 page, got {txt_doc.total_pages}"
    assert "ACME ENTERPRISE" in txt_doc.pages[0].text

    txt_chunks = chunker.split_document(txt_doc)
    assert len(txt_chunks) >= 2, f"Expected at least 2 chunks, got {len(txt_chunks)}"
    for c in txt_chunks:
        assert c.filename == "company_handbook.txt"
        assert c.page_number == 1
        assert c.chunk_id.startswith("company_handbook.txt_p1_c")
        assert len(c.text) <= 350

    # Test CSV Loading & Chunking
    csv_doc = loader.load(str(sample_csv))
    assert csv_doc.total_pages == 1
    assert "Engineering" in csv_doc.pages[0].text
    csv_chunks = chunker.split_document(csv_doc)
    assert len(csv_chunks) >= 1
    assert csv_chunks[0].filename == "q3_financials.csv"

    # Test PDF Loading (blank pages handling)
    pdf_doc = loader.load(str(sample_pdf))
    assert pdf_doc.total_pages == 2

    # Verify no emojis in logs
    for stage, msg in logs:
        for ch in msg:
            assert ord(ch) < 10000, f"Emoji or non-ascii decorative character found in log: {msg}"

    print("\nALL_LOADER_AND_SPLITTER_TESTS_PASSED_SUCCESSFULLY")

if __name__ == "__main__":
    test_loader_and_splitter()
