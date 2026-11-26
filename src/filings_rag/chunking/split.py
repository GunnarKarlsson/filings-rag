"""Structure-aware text splitting (size + overlap)."""

from __future__ import annotations

# ~600 tokens at ~4 chars/token; ~12% overlap. No tokenizer dependency in Step 5.
DEFAULT_CHUNK_CHARS = 2400
DEFAULT_OVERLAP_CHARS = 300

_SEPARATORS = ("\n\n", "\n", ". ", " ")


def split_text(
    text: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[tuple[int, int, str]]:
    """
    Split text into overlapping windows.

    Returns list of (start_offset, end_offset, piece) in the original string.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [(0, len(text), text)]

    if overlap_chars >= chunk_chars:
        raise ValueError("overlap_chars must be smaller than chunk_chars")

    pieces: list[tuple[int, int, str]] = []
    start = 0
    n = len(text)
    while start < n:
        ideal_end = min(start + chunk_chars, n)
        end = ideal_end
        if ideal_end < n:
            window = text[start:ideal_end]
            split_at: int | None = None
            for sep in _SEPARATORS:
                idx = window.rfind(sep)
                # Prefer a break in the latter half so chunks stay near target size.
                if idx >= chunk_chars // 2:
                    split_at = start + idx + len(sep)
                    break
            if split_at is not None:
                end = split_at
        piece = text[start:end].strip()
        if piece:
            # Recompute offsets against stripped piece inside [start:end].
            rel = text[start:end].find(piece)
            abs_start = start + max(rel, 0)
            abs_end = abs_start + len(piece)
            pieces.append((abs_start, abs_end, piece))
        if end >= n:
            break
        next_start = max(end - overlap_chars, start + 1)
        if next_start <= start:
            next_start = end
        start = next_start
    return pieces
