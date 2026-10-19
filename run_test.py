import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.core.rag_engine import RAGEngine

def main():
    print("=" * 60)
    print("ENTERPRISE KNOWLEDGE RAG ENGINE - TEST RUNNER")
    print("=" * 60)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    mock_mode = False

    is_placeholder = (
        not api_key
        or api_key == "your_gemini_api_key_here"
        or api_key.startswith("your_")
    )

    if is_placeholder:
        print("\n[NOTICE] GEMINI_API_KEY in .env is either unset or still the placeholder.")
        print("[NOTICE] Running in deterministic offline test mode.")
        print("[NOTICE] To connect live with Google Gemini, replace 'your_gemini_api_key_here' in .env")
        print("         with your free key from https://aistudio.google.com/app/apikey\n")
        mock_mode = True
    else:
        print("[CONFIG] Live Gemini API Key detected.")
        print(f"[CONFIG] Generation Model: {os.getenv('GEMINI_CHAT_MODEL', 'gemini-3.5-flash-lite')}")
        print(f"[CONFIG] Embedding Model:  {os.getenv('GEMINI_EMBED_MODEL', 'gemini-embedding-001')}\n")

    def telemetry(stage: str, message: str, data: dict):
        print(f"[{stage}] {message}")

    engine = RAGEngine(
        persist_dir="./data/chroma_db",
        progress_callback=telemetry,
        mock_mode=mock_mode
    )

    # Prompt or take argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        default_file = str(Path("./tests/sample_data/company_handbook.txt").resolve())
        print(f"Default sample document available: {default_file}")
        user_input = input("Enter document file path (press Enter for sample): ").strip().strip('"').strip("'")
        file_path = user_input if user_input else default_file

    path_obj = Path(file_path)
    if not path_obj.exists():
        print(f"\n[ERROR] File not found: {file_path}")
        return

    print("\n--- STAGE 1: INGESTION PIPELINE ---")
    result = engine.ingest_file(file_path)
    print(f"\n[SUMMARY] Ingested {result['filename']}: {result['chunks_indexed']} chunks across {result['total_pages']} pages in {result['elapsed_seconds']}s")

    print("\n--- STAGE 2: INTERACTIVE QUERY CONSOLE ---")
    print("Type your question to test retrieval and citation grounding. (Type 'exit' to quit)\n")

    while True:
        try:
            query = input("\nEnter query: ").strip()
            if not query:
                continue
            if query.lower() in {"exit", "quit", "q"}:
                print("\nExiting test runner.")
                break

            print("-" * 50)
            response = engine.query(query, top_k=3)
            print("-" * 50)

            print("\nGROUNDED ANSWER:")
            print(response.answer)

            if response.citations:
                print(f"\nCITATIONS & EVIDENCE ({len(response.citations)} references):")
                for c in response.citations:
                    print(f"\n  [Citation {c.citation_id}]")
                    print(f"  Source File:  {c.source_filename}")
                    print(f"  Page Number:  {c.page_number}")
                    print(f"  Relevance:    {c.similarity_score * 100:.1f}%")
                    print(f"  Excerpt:      \"{c.excerpt[:180]}...\"")
            else:
                print("\n[No citations available for this response]")

            print(f"\n[Telemetry: Processed in {response.processing_time_ms}ms, {response.total_chunks_evaluated} candidates evaluated]")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting test runner.")
            break

if __name__ == "__main__":
    main()
