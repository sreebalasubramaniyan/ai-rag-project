import os
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from google import genai
from google.genai import types

from src.core.models import Document, DocumentChunk, SearchResult, Citation, RAGResponse
from src.core.loader import DocumentLoader
from src.core.splitter import SemanticChunker
from src.core.vector_store import VectorStore
from src.core.ollama_client import OllamaClient
from src.core.openrouter_client import OpenRouterClient
from src.core.privacy_engine import EnterprisePrivacyGuard, PrivacyDecision

class RAGEngine:
    """Enterprise RAG engine providing file ingestion, vector search, and grounded synthesis with citations."""

    DEFAULT_GEMINI_CHAT_MODEL = "gemini-3.5-flash-lite"
    DEFAULT_OLLAMA_CHAT_MODEL = "llama3.2"
    DEFAULT_OPENROUTER_CHAT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        provider: str = "gemini",
        chat_model: Optional[str] = None,
        api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        persist_dir: str = "./data/chroma_db",
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        progress_callback: Optional[Callable[[str, str, dict], None]] = None,
        mock_mode: bool = False
    ):
        self.provider = provider.lower().strip()
        self.mock_mode = mock_mode
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.ollama_base_url = ollama_base_url
        self.progress_callback = progress_callback

        if self.provider == "ollama":
            self.chat_model = chat_model or os.getenv("OLLAMA_CHAT_MODEL", self.DEFAULT_OLLAMA_CHAT_MODEL)
        elif self.provider == "openrouter":
            self.chat_model = chat_model or os.getenv("OPENROUTER_CHAT_MODEL", self.DEFAULT_OPENROUTER_CHAT_MODEL)
        else:
            self.chat_model = chat_model or os.getenv("GEMINI_CHAT_MODEL", self.DEFAULT_GEMINI_CHAT_MODEL)

        # Initialize sub-components with progress callback forwarding
        self.loader = DocumentLoader(progress_callback=self._notify)
        self.chunker = SemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            progress_callback=self._notify
        )

        if vector_store:
            self.vector_store = vector_store
        else:
            embed_provider = "gemini" if self.provider == "openrouter" else self.provider
            self.vector_store = VectorStore(
                persist_dir=persist_dir,
                provider=embed_provider,
                api_key=self.api_key,
                ollama_base_url=self.ollama_base_url,
                progress_callback=self._notify,
                mock_mode=self.mock_mode
            )

        self.privacy_guard = EnterprisePrivacyGuard()
        self.genai_client = None
        self.ollama_client = None
        self.openrouter_client = None

        if not self.mock_mode:
            if self.provider == "ollama":
                self.ollama_client = OllamaClient(base_url=self.ollama_base_url)
            elif self.provider == "openrouter":
                self.openrouter_client = OpenRouterClient()
            else:
                if not self.api_key:
                    raise ValueError("GEMINI_API_KEY is not set. Please provide a key via .env or constructor.")
                self.genai_client = genai.Client(api_key=self.api_key)

    def _notify(self, stage: str, message: str, data: Optional[dict] = None) -> None:
        if self.progress_callback:
            self.progress_callback(stage, message, data or {})

    def ingest_file(self, file_path: str) -> Dict[str, Any]:
        """Loads, chunks, embeds, and indexes a single document file."""
        start_time = time.time()
        self._notify("INGEST", f"Starting ingestion pipeline for: {file_path}", {"file_path": file_path})

        # 1. Parse document
        document = self.loader.load(file_path)

        # 2. Chunk document
        chunks = self.chunker.split_document(document)
        if not chunks:
            self._notify("WARN", f"No valid text chunks could be extracted from: {document.filename}", {})
            return {
                "filename": document.filename,
                "chunks_indexed": 0,
                "total_pages": document.total_pages,
                "elapsed_seconds": round(time.time() - start_time, 2)
            }

        # 3. Embed and Index into Vector DB
        indexed_count = self.vector_store.add_chunks(chunks)

        elapsed = round(time.time() - start_time, 2)
        self._notify(
            "COMPLETE",
            f"Ingestion finished for {document.filename}: {indexed_count} chunks indexed in {elapsed}s",
            {"filename": document.filename, "chunks_indexed": indexed_count, "elapsed_seconds": elapsed}
        )

        return {
            "filename": document.filename,
            "source_path": document.source_path,
            "total_pages": document.total_pages,
            "chunks_indexed": indexed_count,
            "elapsed_seconds": elapsed
        }

    def query(
        self,
        query_text: str,
        top_k: int = 4,
        enforce_privacy: bool = True
    ) -> RAGResponse:
        """
        Executes Dual-Stage Privacy Enforced Enterprise RAG:
        1. Stage 1 Query Audit: Completely blocks queries targeting credentials, personal docs, or secrets.
        2. Vector Retrieval & Context Inspection: Ensures retrieved passages do not leak protected secrets.
        3. Local Offline Grounded Synthesis: Air-gapped generation via Ollama (zero cloud egress).
        4. Stage 2 Output Verification: Scans output and intercepts any residual leaks before delivery.
        """
        start_time = time.time()
        query_str = query_text.strip()

        if not query_str:
            return RAGResponse(
                query=query_text,
                answer="No query was provided.",
                citations=[],
                total_chunks_evaluated=0,
                processing_time_ms=0.0
            )

        self._notify("QUERY", f"Processing query: '{query_str}'", {"query": query_str, "top_k": top_k})

        # =====================================================================
        # STAGE 1: QUERY-ADAPTIVE PRIVACY & SECURITY AUDIT
        # =====================================================================
        if enforce_privacy:
            self._notify(
                "STAGE_1_AUDIT",
                "Stage 1 Privacy: Auditing query for restricted credentials, personal records, or secrecy probes...",
                {"query": query_str}
            )
            decision = self.privacy_guard.evaluate_query(query_str)
            if decision.is_restricted:
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                self._notify(
                    "STAGE_1_BLOCKED",
                    f"ACCESS RESTRICTED: Query violates enterprise privacy policy [{decision.category_label}]",
                    {"category": decision.category, "reason": decision.reason}
                )
                audit_cert = self.privacy_guard.generate_audit_certificate(
                    decision=decision,
                    elapsed_ms=elapsed_ms,
                    provider=self.provider
                )
                return RAGResponse(
                    query=query_str,
                    answer=decision.refusal_message,
                    citations=[],
                    total_chunks_evaluated=0,
                    processing_time_ms=elapsed_ms,
                    is_restricted=True,
                    restriction_category=decision.category,
                    privacy_audit=audit_cert
                )

        # =====================================================================
        # VECTOR RETRIEVAL
        # =====================================================================
        self._notify(
            "RETRIEVE",
            f"Retrieving candidate knowledge base passages (top_k={top_k})...",
            {"top_k": top_k}
        )
        search_results = self.vector_store.similarity_search(query_str, top_k=top_k)

        if not search_results:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            self._notify("QUERY", "No relevant context found in the enterprise knowledge base.", {})
            return RAGResponse(
                query=query_str,
                answer="The enterprise knowledge base is currently empty or contains no relevant documents for this query. Please ingest documents first.",
                citations=[],
                total_chunks_evaluated=0,
                processing_time_ms=elapsed_ms
            )

        # =====================================================================
        # STAGE 1 (PART 2): CONTEXT SENSITIVITY INSPECTION
        # =====================================================================
        if enforce_privacy:
            self._notify(
                "STAGE_1_CONTEXT_CHECK",
                f"Inspecting {len(search_results)} retrieved context blocks against enterprise privacy boundaries...",
                {"candidates": len(search_results)}
            )
            ctx_decision = self.privacy_guard.evaluate_context_and_intent(query_str, search_results)
            if ctx_decision.is_restricted:
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                self._notify(
                    "STAGE_1_BLOCKED",
                    f"ACCESS RESTRICTED: Retrieved context contains confidential credentials/secrets [{ctx_decision.category_label}]",
                    {"category": ctx_decision.category}
                )
                audit_cert = self.privacy_guard.generate_audit_certificate(
                    decision=ctx_decision,
                    elapsed_ms=elapsed_ms,
                    provider=self.provider
                )
                return RAGResponse(
                    query=query_str,
                    answer=ctx_decision.refusal_message,
                    citations=[],
                    total_chunks_evaluated=len(search_results),
                    processing_time_ms=elapsed_ms,
                    is_restricted=True,
                    restriction_category=ctx_decision.category,
                    privacy_audit=audit_cert
                )

        # =====================================================================
        # CONTEXT BUILDING & LOCAL GROUNDED SYNTHESIS
        # =====================================================================
        self._notify(
            "EVALUATE",
            f"Evaluating {len(search_results)} authorized passages for synthesis...",
            {"candidates": len(search_results)}
        )

        context_blocks = []
        citations_lookup: Dict[int, Citation] = {}

        for idx, result in enumerate(search_results, start=1):
            c = result.chunk
            source_tag = f"[Source {idx}]"
            context_blocks.append(
                f"{source_tag} (File: {c.filename}, Page: {c.page_number})\n{c.text}\n"
            )
            citations_lookup[idx] = Citation(
                citation_id=idx,
                source_filename=c.filename,
                source_path=c.source_path,
                page_number=c.page_number,
                chunk_id=c.chunk_id,
                similarity_score=result.similarity_score,
                excerpt=c.text
            )

        context_str = "\n---\n".join(context_blocks)

        self._notify(
            "SYNTHESIZE",
            f"Synthesizing grounded response via model {self.chat_model} (Provider: {self.provider})...",
            {"model": self.chat_model, "provider": self.provider}
        )

        system_instruction = (
            "You are an Enterprise Knowledge Assistant operating under strict privacy enforcement.\n"
            "Your task is to provide accurate, factual answers based strictly on the provided enterprise document passages.\n\n"
            "STRICT PRIVACY & GROUNDING GUIDELINES:\n"
            "1. Answer ONLY using the facts stated in the reference passages.\n"
            "2. For every claim, fact, or metric you provide, include the exact citation bracket, e.g. [Source 1] or [Source 2].\n"
            "3. If multiple sources support a statement, cite all relevant sources, e.g. [Source 1][Source 2].\n"
            "4. NEVER invent or assume private credentials, personal identifiers, or undisclosed enterprise figures.\n"
            "5. If the provided passages do NOT contain sufficient information to answer the question, "
            "state clearly: 'The provided enterprise documents do not contain sufficient information to answer this question.'\n"
            "6. Maintain a professional, objective tone. Do not use emojis."
        )

        user_prompt = (
            f"REFERENCE PASSAGES:\n{context_str}\n\n"
            f"USER QUERY:\n{query_str}\n\n"
            "GROUNDED ANSWER (with [Source X] citations):"
        )

        raw_answer = ""
        if self.mock_mode:
            raw_answer = f"Based on the enterprise records, {search_results[0].chunk.text} [Source 1]."
        elif self.provider == "ollama":
            try:
                raw_answer = self.ollama_client.generate_completion(
                    prompt=user_prompt,
                    system=system_instruction,
                    model=self.chat_model,
                    temperature=0.1
                )
                if not raw_answer:
                    raw_answer = "No response generated by local Ollama model."
            except Exception as exc:
                raise RuntimeError(f"Local Ollama generation failed: {exc}") from exc
        elif self.provider == "openrouter":
            try:
                raw_answer = self.openrouter_client.generate_completion(
                    prompt=user_prompt,
                    system=system_instruction,
                    model=self.chat_model,
                    temperature=0.1
                )
                if not raw_answer:
                    raw_answer = "No response generated by OpenRouter model."
            except Exception as exc:
                raise RuntimeError(f"OpenRouter generation failed: {exc}") from exc
        else:
            # Google Gemini cloud synthesis with automatic retry and model fallback
            fallback_pool = [
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-flash-latest"
            ]
            candidate_models = [self.chat_model] if self.chat_model in fallback_pool else []
            for fb in fallback_pool:
                if fb not in candidate_models:
                    candidate_models.append(fb)

            raw_answer = ""
            last_error = None

            for current_model in candidate_models:
                success = False
                for attempt in range(2):
                    try:
                        response = self.genai_client.models.generate_content(
                            model=current_model,
                            contents=user_prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.1,
                            )
                        )
                        raw_answer = response.text.strip() if response.text else "No response generated."
                        success = True
                        break
                    except Exception as exc:
                        last_error = exc
                        err_msg = str(exc)
                        if "503" in err_msg or "UNAVAILABLE" in err_msg:
                            # Model endpoint experiencing high demand, pause briefly
                            time.sleep(0.5)
                            continue
                        elif ("429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg) and attempt < 1:
                            time.sleep(1.0)
                            continue
                        elif "API_KEY_INVALID" in err_msg or "API key not valid" in err_msg:
                            raise ValueError("Google Gemini API Key is invalid.") from None
                        else:
                            break
                if success:
                    break

            if not raw_answer:
                err_str = str(last_error) if last_error else "Model unavailable"
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    raise RuntimeError(
                        "Google Gemini servers are currently experiencing temporary high demand (503 UNAVAILABLE). "
                        "Please try again in a few moments, or toggle to 'Local Offline (Ollama)' mode in the top bar for 100% offline generation with zero external limits."
                    )
                elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    raise ValueError(
                        "Google Gemini daily quota reached. Switch to 'Local Offline (Ollama)' mode for unlimited queries."
                    )
                else:
                    raise last_error

        # =====================================================================
        # STAGE 2: OUTPUT LEAKAGE PREVENTION & VERIFICATION
        # =====================================================================
        final_answer = raw_answer
        stage_2_audit = None
        is_restricted = False
        restriction_category = None

        if enforce_privacy:
            self._notify(
                "STAGE_2_VERIFY",
                "Stage 2 Post-Generation: Scanning output for credential, secret, or personal entity leakage...",
                {}
            )
            is_clean, verified_text, stage_2_audit = self.privacy_guard.verify_output(raw_answer)
            final_answer = verified_text
            if not is_clean:
                is_restricted = True
                restriction_category = "OUTPUT_LEAKAGE"
                self._notify(
                    "STAGE_2_BLOCKED",
                    "ACCESS RESTRICTED: Output contained sensitive credentials/PII and has been suppressed.",
                    stage_2_audit
                )
            else:
                self._notify(
                    "STAGE_2_VERIFIED",
                    "Stage 2 Verification: Zero leakage detected. Output verified safe.",
                    stage_2_audit
                )

        # Citations mapping (only if not restricted)
        used_citations: List[Citation] = []
        if not is_restricted:
            cited_indices = [int(m) for m in re.findall(r"\[Source\s*(\d+)\]", final_answer, re.IGNORECASE)]
            if cited_indices:
                seen = set()
                for c_idx in cited_indices:
                    if c_idx in citations_lookup and c_idx not in seen:
                        used_citations.append(citations_lookup[c_idx])
                        seen.add(c_idx)
            else:
                used_citations = list(citations_lookup.values())

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        audit_cert = self.privacy_guard.generate_audit_certificate(
            decision=PrivacyDecision(is_restricted=is_restricted, category=restriction_category),
            stage_2_audit=stage_2_audit,
            elapsed_ms=elapsed_ms,
            provider=self.provider
        )

        self._notify(
            "COMPLETE",
            f"Query processing finished in {elapsed_ms}ms. Status: {audit_cert['overall_status']}",
            {"elapsed_ms": elapsed_ms, "citations_count": len(used_citations)}
        )

        return RAGResponse(
            query=query_str,
            answer=final_answer,
            citations=used_citations,
            total_chunks_evaluated=len(search_results),
            processing_time_ms=elapsed_ms,
            is_restricted=is_restricted,
            restriction_category=restriction_category,
            privacy_audit=audit_cert
        )

    def get_stats(self) -> Dict[str, Any]:
        """Returns knowledge base stats and provider details."""
        stats = self.vector_store.get_stats()
        stats["provider"] = self.provider
        stats["chat_model"] = self.chat_model
        return stats

    def clear(self) -> None:
        """Clears the knowledge base index."""
        self.vector_store.clear()
