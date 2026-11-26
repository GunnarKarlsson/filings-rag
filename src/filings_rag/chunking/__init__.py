"""Turn parsed 10-K sections into overlapping text chunks."""

from filings_rag.chunking.build import chunks_for_filing
from filings_rag.chunking.model import Chunk
from filings_rag.chunking.split import split_text

__all__ = ["Chunk", "chunks_for_filing", "split_text"]
