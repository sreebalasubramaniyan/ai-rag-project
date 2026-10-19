import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import chromadb
from chromadb.config import Settings
from google import genai
from google.genai import types

from src.core.models import DocumentChunk, SearchResult
from src.core.ollama_client import OllamaClient

class VectorStore:
    """Persistent ChromaDB vector store backed by Google Gemini or local Ollama embeddings."""

    DEFAULT_COLLECTION_NAME = "enterprise_knowledge"
    DEFAULT_GEMINI_EMBED_MODEL = "gemini-embedding-001"
    DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"

    def __init__(
        self,
        persist_dir: str = "./data/chroma_db",
        collection_name: str = DEFAULT_COLLECTION_NAME,
        provider: str = "gemini",
        embed_model: Optional[str] = None,
        api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        progress_callback: Optional[Callable[[str, str, dict], None]] = None,
        mock_mode: bool = False
    ):
        self.persist_dir = str(Path(persist_dir).resolve())
        self.provider = provider.lower().strip()
        self.mock_mode = mock_mode
        self.progress_callback = progress_callback

        if self.provider == "ollama":
            self.embed_model = embed_model or os.getenv("OLLAMA_EMBED_MODEL", self.DEFAULT_OLLAMA_EMBED_MODEL)
        else:
            self.embed_model = embed_model or os.getenv("GEMINI_EMBED_MODEL", self.DEFAULT_GEMINI_EMBED_MODEL)

        model_suffix = self.embed_model.replace("/", "_").replace("-", "_").replace(":", "_")
        self.collection_name = f"{collection_name}_{self.provider}_{model_suffix}"

        # Initialize clients according to provider
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.genai_client = None
        self.ollama_client = None

        if not self.mock_mode:
            if self.provider == "ollama":
                self.ollama_client = OllamaClient(base_url=ollama_base_url)
            else:
                if not self.api_key:
                    raise ValueError(
                        "GEMINI_API_KEY is not set. Please provide a valid key via .env or constructor."
                    )
                self.genai_client = genai.Client(api_key=self.api_key)

        # Initialize ChromaDB persistent client
        os.makedirs(self.persist_dir, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def _notify(self, stage: str, message: str, data: Optional[dict] = None) -> None:
        if self.progress_callback:
            self.progress_callback(stage, message, data or {})

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings using Gemini or local Ollama with fallback mock mode."""
        if self.mock_mode:
            # Deterministic pseudo-embedding for testing without API or daemon usage
            dim = 768 if self.provider == "ollama" else 3072
            vectors = []
            for text in texts:
                h = abs(hash(text))
                vector = [((h >> (i % 32)) & 0xFF) / 255.0 for i in range(dim)]
                vectors.append(vector)
            return vectors

        if self.provider == "ollama":
            return self.ollama_client.generate_embeddings(texts=texts, model=self.embed_model)

        # Gemini API embedding
        try:
            response = self.genai_client.models.embed_content(
                model=self.embed_model,
                contents=texts
            )
            return [emb.values for emb in response.embeddings]
        except Exception as exc:
            err_msg = str(exc)
            if "API_KEY_INVALID" in err_msg or "API key not valid" in err_msg:
                raise ValueError(
                    "Google Gemini API Key is invalid. Please check your GEMINI_API_KEY in the .env file. "
                    "You can get a free key from Google AI Studio at: https://aistudio.google.com/app/apikey"
                ) from None
            raise

    def add_chunks(self, chunks: List[DocumentChunk], batch_size: int = 25) -> int:
        """Embeds and indexes document chunks into persistent ChromaDB."""
        if not chunks:
            return 0

        total = len(chunks)
        self._notify(
            "EMBED",
            f"Preparing to embed {total} chunk{'s' if total != 1 else ''} with model {self.embed_model}",
            {"total_chunks": total, "model": self.embed_model}
        )

        all_ids = []
        all_embeddings = []
        all_documents = []
        all_metadatas = []

        total_batches = (total + batch_size - 1) // batch_size
        for batch_idx in range(0, total, batch_size):
            batch_num = (batch_idx // batch_size) + 1
            batch = chunks[batch_idx : batch_idx + batch_size]
            batch_texts = [c.text for c in batch]

            self._notify(
                "EMBED",
                f"Generating embeddings for batch {batch_num}/{total_batches} ({len(batch)} chunks)",
                {"batch_number": batch_num, "total_batches": total_batches, "batch_size": len(batch)}
            )

            batch_vectors = self._generate_embeddings(batch_texts)

            for chunk, vector in zip(batch, batch_vectors):
                all_ids.append(chunk.chunk_id)
                all_embeddings.append(vector)
                all_documents.append(chunk.text)
                all_metadatas.append({
                    "source_path": chunk.source_path,
                    "filename": chunk.filename,
                    "page_number": int(chunk.page_number),
                    "chunk_index": int(chunk.chunk_index),
                    "char_count": int(chunk.char_count)
                })

        self._notify(
            "INDEX",
            f"Writing {len(all_ids)} vectorized chunks to ChromaDB storage at {self.persist_dir}",
            {"count": len(all_ids), "persist_dir": self.persist_dir}
        )

        # Upsert into ChromaDB
        self.collection.upsert(
            ids=all_ids,
            embeddings=all_embeddings,
            documents=all_documents,
            metadatas=all_metadatas
        )

        self._notify(
            "INDEX",
            f"Successfully indexed {len(all_ids)} chunks into collection '{self.collection_name}'",
            {"count": len(all_ids), "collection": self.collection_name}
        )

        return len(all_ids)

    def similarity_search(self, query: str, top_k: int = 4) -> List[SearchResult]:
        """Performs vector similarity search against the knowledge base."""
        query_text = query.strip()
        if not query_text:
            return []

        self._notify(
            "SEARCH",
            f"Vectorizing query and executing similarity search (top_k={top_k})",
            {"query": query_text, "top_k": top_k}
        )

        query_vectors = self._generate_embeddings([query_text])
        query_vector = query_vectors[0]

        count = self.collection.count()
        if count == 0:
            self._notify("SEARCH", "Knowledge base is empty. 0 results returned.", {"count": 0})
            return []

        actual_k = min(top_k, count)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"]
        )

        search_results: List[SearchResult] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return search_results

        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for chunk_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
            # Cosine distance ranges from 0 (identical) to 2 (opposite).
            # Convert to similarity score between 0.0 and 1.0
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))

            chunk = DocumentChunk(
                chunk_id=chunk_id,
                text=doc_text,
                source_path=meta.get("source_path", ""),
                filename=meta.get("filename", "unknown"),
                page_number=int(meta.get("page_number", 1)),
                chunk_index=int(meta.get("chunk_index", 0)),
                char_count=int(meta.get("char_count", len(doc_text))),
                metadata=meta
            )
            search_results.append(SearchResult(
                chunk=chunk,
                similarity_score=round(similarity, 4),
                distance=round(dist, 4)
            ))

        self._notify(
            "SEARCH",
            f"Found {len(search_results)} relevant passage{'s' if len(search_results) != 1 else ''}",
            {"results_count": len(search_results)}
        )

        return search_results

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistical overview of the vector store contents."""
        total_chunks = self.collection.count()
        distinct_files = set()

        if total_chunks > 0:
            data = self.collection.get(include=["metadatas"])
            for meta in data.get("metadatas", []):
                if meta and "filename" in meta:
                    distinct_files.add(meta["filename"])

        return {
            "total_chunks": total_chunks,
            "total_documents": len(distinct_files),
            "documents": sorted(list(distinct_files)),
            "collection_name": self.collection_name,
            "storage_path": self.persist_dir,
            "provider": self.provider,
            "embed_model": self.embed_model
        }

    def clear(self) -> None:
        """Clears all records from the collection."""
        self.chroma_client.delete_collection(name=self.collection_name)
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self._notify("INDEX", f"Cleared all vectors from collection '{self.collection_name}'", {})
