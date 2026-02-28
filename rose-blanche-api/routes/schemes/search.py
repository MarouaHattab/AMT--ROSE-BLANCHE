from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    question: str
    top_k: Optional[int] = 3


class IngestRequest(BaseModel):
    chunk_size: Optional[int] = None
    overlap_size: Optional[int] = None
    directory_path: Optional[str] = None
