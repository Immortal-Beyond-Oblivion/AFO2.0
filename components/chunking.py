# components/chunking.py
"""
T019: minimal text-chunking helper for embedding per-file content.

architecture.md §2.2 calls for "chunked embeddings (e.g. 500-800 tokens/chunk)
for long documents, with the parent file_id attached to every chunk so a hit
rolls back up to a file-level result." This module does the chunking half of
that; retriever.py does the embedding/storage half.

Deliberately character-based, not token-based: adding a tokenizer (e.g.
tiktoken) purely to size chunks "correctly" would be a new dependency for a
fairly small precision gain, given the embedding model itself
(sentence-transformers) has its own truncation limit regardless. A
conservative chars-per-token estimate (~4 chars/token for English text) is
used to translate the "500-800 tokens" target into a character-based
default, documented here rather than silently guessed at the call site.
"""

# ~4 chars/token is a standard rough estimate for English text. 700 tokens
# (mid-point of architecture.md's 500-800 target) * 4 ≈ 2800 chars.
DEFAULT_CHUNK_SIZE_CHARS = 2800
# A modest overlap so a concept split across a chunk boundary is still
# findable from either side, without duplicating so much content that the
# vector index bloats.
DEFAULT_CHUNK_OVERLAP_CHARS = 300


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """
    Split `text` into a list of overlapping chunks, each at most `chunk_size`
    characters. Returns an empty list for empty/whitespace-only input rather
    than a list containing one empty string, so callers can treat "no
    chunks" as "nothing to index" without an extra check.

    If `text` is shorter than `chunk_size`, the result is a single chunk
    (the whole text, stripped) — most files AFO handles today (short text
    files, one-page PDFs) will hit this path and never actually need
    splitting.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    step = chunk_size - overlap
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start += step

    return chunks
