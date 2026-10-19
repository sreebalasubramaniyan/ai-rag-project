from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class DocumentPage:
    """Represents a single page or section extracted from a source document."""
    page_number: int
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Document:
    """Represents a loaded document with its pages and metadata."""
    source_path: str
    filename: str
    file_type: str
    pages: List[DocumentPage]
    total_pages: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DocumentChunk:
    """Represents a discrete semantic chunk of text for embedding and retrieval."""
    chunk_id: str
    text: str
    source_path: str
    filename: str
    page_number: int
    chunk_index: int
    char_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    sensitivity_level: str = "INTERNAL"

@dataclass
class SearchResult:
    """Represents a retrieved chunk with similarity metrics."""
    chunk: DocumentChunk
    similarity_score: float
    distance: float

@dataclass
class Citation:
    """Citation reference for verifiable answer grounding."""
    citation_id: int
    source_filename: str
    source_path: str
    page_number: int
    chunk_id: str
    similarity_score: float
    excerpt: str

@dataclass
class RAGResponse:
    """Final grounded response returned to the user with privacy verification audit."""
    query: str
    answer: str
    citations: List[Citation]
    total_chunks_evaluated: int
    processing_time_ms: float
    is_restricted: bool = False
    restriction_category: Optional[str] = None
    privacy_audit: Optional[Dict[str, Any]] = None

