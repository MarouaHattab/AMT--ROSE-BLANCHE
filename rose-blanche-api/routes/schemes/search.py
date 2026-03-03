from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest(BaseModel):
    """
    Semantic search request.
    
    Attributes:
        question: The search query
        top_k: Number of top results to return (default 3)
    """
    question: str = Field(..., min_length=1, max_length=1000, description="Search query")
    top_k: Optional[int] = Field(default=3, ge=1, le=20, description="Number of results")


class IngestRequest(BaseModel):
    """
    Ingestion request (used by data & tasks routes).
    
    Attributes:
        chunk_size: Maximum characters per chunk
        overlap_size: Overlap between consecutive chunks
        directory_path: Optional custom dataset directory
    """
    chunk_size: Optional[int] = Field(default=None, ge=50, le=2000, description="Chunk size")
    overlap_size: Optional[int] = Field(default=None, ge=0, le=500, description="Overlap size")
    directory_path: Optional[str] = Field(default=None, description="Dataset directory path")
