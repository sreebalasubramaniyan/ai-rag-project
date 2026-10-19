# Dual-Stage Privacy Enforcement for Fully Offline Enterprise RAG

**Patent Specification Title**: *"A Fully Offline Privacy-Aware Retrieval-Augmented Generation System with Query-Adaptive Context Filtering and Output Leakage Prevention"*  
*(Alternative Title: "Query-Adaptive Privacy-Preserving Offline RAG System for Enterprise Knowledge Management")*

---

## Technical Innovation & Architecture Overview

Enterprise knowledge retrieval often faces two major vulnerability vectors:
1. **Context Contamination (Pre-Generation)**: Blindly injecting top-$k$ retrieved vector passages into an LLM context window exposes confidential data, PII, and out-of-scope secrets.
2. **Output Data Leakage (Post-Generation)**: LLM outputs may reveal confidential corporate entities, credentials, or personal identifiers.

This system introduces a **Dual-Stage Privacy Enforcement Pipeline** combined with a **100% Air-Gapped Local Offline Engine**:

- **Stage 1: Query & Context Privacy Enforcement (Pre-Generation)**:
  - Automatic query-adaptive intent inspection: detects credential probes, password requests, personal employee records, and secrets.
  - Zero Context Injection: immediately halts queries targeting restricted data before any candidate text reaches the LLM prompt.
  - Context sensitivity verification: ensures retrieved passages do not contain unauthorized credentials or sensitive internal files.
- **Stage 2: Output Leakage Prevention (Post-Generation)**:
  - Scans synthesized model outputs for leaked credentials, passwords, tokens, or PII.
  - Intercepts and suppresses unauthorized data before delivery.
  - Generates verifiable cryptographic & policy compliance audit certificates.
- **100% Offline Air-Gapped Operation**:
  - Uses local ChromaDB storage and local Ollama (`llama3.2` + `nomic-embed-text`) with zero cloud egress.
  - Also supports optional hybrid cloud mode (Google Gemini).

> **Important Patent Distinction**:  
> *Ollama and ChromaDB serve as the local execution runtime. The proprietary invention is the **Dual-Stage Privacy Enforcement (Context Filtering + Output Verification)** architecture.*

---

## System Workflow

```text
[ Document Ingestion: PDF, DOCX, TXT, CSV, JSON, MD, Code ]
                         │
                         ▼
[ Semantic Chunking & Structuring ]
                         │
                         ▼
[ Offline Local Embedding & Storage (ChromaDB) ]
                         │
                         ▼
[ User Submits Enterprise Query ]
                         │
                         ▼
[ STAGE 1: Query & Context Privacy Enforcement ]
   ├── Prohibited Query (Credentials/Secrets):
   │   └── IMMEDIATELY BLOCKED: Emits Access Restricted Notice. Zero LLM prompt injection.
   └── Legitimate Operational Query:
       └── Top-k Vector Similarity Retrieval & Context Verification
                         │
                         ▼
[ Grounded Local Synthesis (Ollama Llama 3.2) ]
   └── 100% Localhost air-gapped generation with [Source X] citations
                         │
                         ▼
[ STAGE 2: Output Leakage Prevention Guard ]
   ├── Entity leakage verification scanner
   └── Suppresses leaked tokens & verifies compliance
                         │
                         ▼
[ Delivery: Grounded Answer + Citations + Privacy Audit Certificate ]
```

---

## Setup & Quickstart

### 1. Launch the Server
```powershell
python app.py
```
Open your browser at `http://127.0.0.1:8000`.

### 2. Run Comprehensive Test Suite
```powershell
python tests/test_dual_stage_privacy.py
python tests/test_rag_engine.py
python tests/test_vector_store.py
python tests/test_loader_and_splitter.py
```

---

## API Endpoints

- `POST /api/query`: Executes Dual-Stage Privacy Enforced vector search and synthesis with automated secret data access prevention.
- `GET /api/privacy/policy`: Returns the dual-stage privacy enforcement specifications and air-gap guarantees.
- `GET /api/providers`: Returns provider status (Ollama local offline vs Gemini cloud).
- `POST /api/provider/switch`: Toggles between local offline mode and cloud mode.
- `POST /api/ingest/upload`: Uploads and vectorizes documents with real-time SSE progress telemetry.
- `GET /api/stats`: Returns document and chunk index statistics.
