import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

from src.core.rag_engine import RAGEngine

def parse_args():
    parser = argparse.ArgumentParser(description="Enterprise Knowledge RAG - Terminal CLI")
    parser.add_argument("--file", "-f", type=str, help="Path to document file to ingest")
    parser.add_argument("--query", "-q", type=str, help="Query to run against the knowledge base")
    parser.add_argument("--provider", "-p", type=str, default="gemini", choices=["gemini", "ollama"], help="AI Provider: 'gemini' (cloud) or 'ollama' (offline privacy)")
    parser.add_argument("--clear", action="store_true", help="Clear the vector database index")
    parser.add_argument("--stats", action="store_true", help="Display vector store statistics")
    return parser.parse_args()

def main():
    args = parse_args()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    mock_mode = False
    if args.provider == "gemini" and (not api_key or api_key == "your_gemini_api_key_here" or api_key.startswith("your_")):
        mock_mode = True

    def telemetry_callback(stage: str, message: str, data: dict):
        print(f"[{stage}] {message}")

    engine = RAGEngine(
        persist_dir="./data/chroma_db",
        provider=args.provider,
        progress_callback=telemetry_callback,
        mock_mode=mock_mode
    )

    if args.clear:
        engine.clear()
        print("[INDEX] Knowledge base cleared successfully.")
        return

    if args.stats:
        stats = engine.get_stats()
        print("\n--- KNOWLEDGE BASE STATISTICS ---")
        print(f"Total Documents: {stats['total_documents']}")
        print(f"Total Chunks:    {stats['total_chunks']}")
        print(f"Collection:      {stats['collection_name']}")
        if stats['documents']:
            print("Documents List:")
            for d in stats['documents']:
                print(f"  - {d}")
        return

    # Ingest file if passed via CLI argument
    if args.file:
        path = Path(args.file).resolve()
        if not path.exists():
            print(f"[ERROR] File not found: {args.file}")
            sys.exit(1)
        print(f"\n[INGEST] Ingesting document: {path}")
        result = engine.ingest_file(str(path))
        print(f"[SUMMARY] Indexed {result['filename']}: {result['chunks_indexed']} chunks in {result['elapsed_seconds']}s")

    # Run query if passed via CLI argument
    if args.query:
        print(f"\n[QUERY] Running: '{args.query}'")
        res = engine.query(args.query, top_k=4)
        print("\n" + "=" * 60)
        print("GROUNDED ANSWER:")
        print("=" * 60)
        print(res.answer)

        if res.citations:
            print("\n" + "-" * 60)
            print(f"CITATIONS & EVIDENCE ({len(res.citations)} references):")
            print("-" * 60)
            for c in res.citations:
                print(f"\n[Citation {c.citation_id}]")
                print(f"  Source:     {c.source_filename} (Page {c.page_number})")
                print(f"  Relevance:  {c.similarity_score * 100:.1f}%")
                print(f"  Excerpt:    \"{c.excerpt[:200]}...\"")
        print(f"\n[Telemetry: {res.processing_time_ms}ms, {res.total_chunks_evaluated} candidates evaluated]")
        return

    # Interactive REPL mode if no query flag provided
    if not args.file and not args.query:
        print("=" * 60)
        print("ENTERPRISE KNOWLEDGE RAG - TERMINAL CONSOLE")
        print("=" * 60)
        if mock_mode:
            print("[NOTICE] Running in deterministic offline test mode.")
            print("[NOTICE] To use live Gemini 2.0 Flash, add valid GEMINI_API_KEY to .env\n")
        else:
            print("[CONFIG] Live Google Gemini 2.0 Flash & text-embedding-004 active.\n")

        # Interactive file prompt
        file_input = input("Enter file path to ingest (or press Enter to skip to query): ").strip().strip('"').strip("'")
        if file_input:
            path = Path(file_input).resolve()
            if path.exists():
                engine.ingest_file(str(path))
            else:
                print(f"[ERROR] File not found: {file_input}")

        print("\nEnter questions to query knowledge base (type 'exit' to quit):")
        while True:
            try:
                q = input("\nQuery: ").strip()
                if not q:
                    continue
                if q.lower() in {"exit", "quit", "q"}:
                    print("Exiting console.")
                    break

                res = engine.query(q, top_k=4)
                print("\nGROUNDED ANSWER:")
                print(res.answer)

                if res.citations:
                    print(f"\nCITATIONS ({len(res.citations)} references):")
                    for c in res.citations:
                        print(f"  - [Source {c.citation_id}] {c.source_filename}, Page {c.page_number} ({c.similarity_score*100:.1f}% relevance)")
                        print(f"    Excerpt: \"{c.excerpt[:150]}...\"")
            except (KeyboardInterrupt, EOFError):
                print("\nExiting console.")
                break

if __name__ == "__main__":
    main()
