from sentence_transformers import SentenceTransformer
from typing import List, Union
import numpy as np
import logging

logger = logging.getLogger("uvicorn")


class EmbeddingService:
    def __init__(self, model_id: str = "all-MiniLM-L6-v2"):
        self.model_id = model_id
        self.model = None
        self.embedding_size = 384

    def load_model(self):
        """Load the sentence-transformer model."""
        logger.info(f"Loading embedding model: {self.model_id}")
        self.model = SentenceTransformer(self.model_id)
        self.embedding_size = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_size}")

    def embed_text(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        if self.model is None:
            self.load_model()

        if isinstance(text, str):
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()

        embeddings = self.model.encode(text, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()
