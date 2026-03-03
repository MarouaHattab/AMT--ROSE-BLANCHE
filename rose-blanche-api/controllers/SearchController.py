from .BaseController import BaseController
from stores.embedding.EmbeddingService import EmbeddingService
from stores.vectordb.PGVectorProvider import PGVectorProvider
from models.db_schemes import RetrievedFragment
from helpers.config import get_settings
from typing import List, Tuple
import logging

logger = logging.getLogger("uvicorn")


class SearchController(BaseController):
    """
    Semantic search controller.
    
    Pipeline:
      1. Receive question
      2. Generate embedding with all-MiniLM-L6-v2 (384D)
      3. Cosine similarity search against pgvector
      4. Rank results by score descending
      5. Return top K fragments with text + score
    """

    def __init__(self, embedding_service: EmbeddingService,
                 vectordb_client: PGVectorProvider):
        super().__init__()
        self.embedding_service = embedding_service
        self.vectordb_client = vectordb_client
        self.settings = get_settings()

    async def search(
        self, 
        question: str, 
        top_k: int = 3,
    ) -> List[RetrievedFragment]:
        """
        Semantic search pipeline using cosine similarity.
        
        Args:
            question: User query text
            top_k: Number of top results to return (default 3)
            
        Returns:
            List of RetrievedFragment sorted by cosine similarity score descending
        """
        logger.info(f"Semantic search: {question[:100]}...")

        # Step 1: Generate embedding for the question
        question_embedding = self.embedding_service.embed_text(question)

        # Step 2: Cosine similarity search in pgvector
        results = await self.vectordb_client.search_by_vector(
            vector=question_embedding,
            limit=top_k,
        )

        if not results:
            logger.info("No results found")
            return []

        # Step 3: Results are already sorted by score DESC from SQL
        logger.info(
            f"Found {len(results)} results, scores: {[r.score for r in results]}"
        )
        return results
