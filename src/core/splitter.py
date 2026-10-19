import re
from typing import List, Callable, Optional
from src.core.models import Document, DocumentChunk

class SemanticChunker:
    """Recursive semantic text splitter with strict page metadata preservation."""

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        progress_callback: Optional[Callable[[str, str, dict], None]] = None
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly smaller than chunk_size.")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.progress_callback = progress_callback
        self.separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]

    def _notify(self, stage: str, message: str, data: Optional[dict] = None) -> None:
        if self.progress_callback:
            self.progress_callback(stage, message, data or {})

    def split_document(self, document: Document) -> List[DocumentChunk]:
        """Splits all pages of a document into discrete chunks with source and page metadata."""
        chunks: List[DocumentChunk] = []
        global_chunk_idx = 0

        self._notify(
            "CHUNK",
            f"Beginning semantic chunking for {document.filename} (Target size: {self.chunk_size}, Overlap: {self.chunk_overlap})",
            {"filename": document.filename, "chunk_size": self.chunk_size, "overlap": self.chunk_overlap}
        )

        for page in document.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            page_chunks_text = self._split_text(page_text)
            for idx, text in enumerate(page_chunks_text):
                cleaned_text = text.strip()
                if not cleaned_text:
                    continue

                chunk_id = f"{document.filename}_p{page.page_number}_c{global_chunk_idx}"

                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    text=cleaned_text,
                    source_path=document.source_path,
                    filename=document.filename,
                    page_number=page.page_number,
                    chunk_index=global_chunk_idx,
                    char_count=len(cleaned_text),
                    metadata={
                        "page_number": page.page_number,
                        "file_type": document.file_type,
                        "chunk_index": global_chunk_idx,
                    }
                )
                chunks.append(chunk)
                global_chunk_idx += 1

        self._notify(
            "CHUNK",
            f"Generated {len(chunks)} chunks across {document.total_pages} page{'s' if document.total_pages != 1 else ''} for {document.filename}",
            {"total_chunks": len(chunks), "filename": document.filename}
        )

        return chunks

    def _split_text(self, text: str) -> List[str]:
        """Recursively splits text into chunks below chunk_size with overlap."""
        if len(text) <= self.chunk_size:
            return [text]

        return self._recursive_split(text, self.separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        final_chunks: List[str] = []
        separator = separators[-1]
        new_separators = []

        for i, sep in enumerate(separators):
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator else list(text)
        good_splits: List[str] = []

        for s in splits:
            if not s:
                continue
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if new_separators:
                    sub_splits = self._recursive_split(s, new_separators)
                    good_splits.extend(sub_splits)
                else:
                    # Character slice fallback
                    for start in range(0, len(s), self.chunk_size - self.chunk_overlap):
                        good_splits.append(s[start:start + self.chunk_size])

        # Merge splits up to chunk_size with overlap
        current_chunk: List[str] = []
        current_len = 0

        for piece in good_splits:
            piece_len = len(piece) + (len(separator) if current_chunk else 0)
            if current_len + piece_len <= self.chunk_size:
                current_chunk.append(piece)
                current_len += piece_len
            else:
                if current_chunk:
                    joined = separator.join(current_chunk)
                    final_chunks.append(joined)
                    # Keep overlap from the end
                    overlap_pieces = []
                    overlap_len = 0
                    for p in reversed(current_chunk):
                        if overlap_len + len(p) <= self.chunk_overlap:
                            overlap_pieces.insert(0, p)
                            overlap_len += len(p)
                        else:
                            break
                    current_chunk = overlap_pieces
                    current_len = sum(len(p) for p in current_chunk) + (len(separator) * (len(current_chunk) - 1) if current_chunk else 0)

                current_chunk.append(piece)
                current_len += len(piece) + (len(separator) if len(current_chunk) > 1 else 0)

        if current_chunk:
            final_chunks.append(separator.join(current_chunk))

        return final_chunks
