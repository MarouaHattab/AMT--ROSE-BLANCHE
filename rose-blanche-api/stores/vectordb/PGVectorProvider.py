from .VectorDBEnums import DistanceMethodEnums
from models.db_schemes import Embedding, RetrievedFragment
from sqlalchemy.future import select
from sqlalchemy.sql import text as sql_text
from typing import List, Optional
import logging


class PGVectorProvider:
    def __init__(self, db_client, default_vector_size: int = 384,
                 distance_method: str = "cosine"):
        self.db_client = db_client
        self.default_vector_size = default_vector_size
        self.distance_method = distance_method
        self.logger = logging.getLogger("uvicorn")

    async def connect(self):
        """Enable pgvector extension in PostgreSQL."""
        async with self.db_client() as session:
            async with session.begin():
                try:
                    await session.execute(sql_text(
                        "CREATE EXTENSION IF NOT EXISTS vector"
                    ))
                    await session.commit()
                except Exception as e:
                    if "already exists" in str(e) or "duplicate key" in str(e).lower():
                        self.logger.info("Vector extension already exists, continuing...")
                        await session.rollback()
                    else:
                        raise e

    async def disconnect(self):
        pass

    async def search_by_vector(self, vector: list, limit: int = 3) -> List[RetrievedFragment]:
        """
        Semantic search using pgvector cosine similarity.
        
        Computes: score = 1 - (vecteur <=> query_vector)
        Orders by score DESC and returns top K fragments.
        """
        vector_str = "[" + ",".join([str(v) for v in vector]) + "]"

        async with self.db_client() as session:
            async with session.begin():
                search_sql = sql_text(
                    "SELECT texte_fragment, id_document, "
                    "1 - (vecteur <=> :vector) as score "
                    "FROM embeddings "
                    "ORDER BY score DESC "
                    "LIMIT :limit"
                )

                result = await session.execute(search_sql, {
                    "vector": vector_str,
                    "limit": limit
                })
                records = result.fetchall()

                return [
                    RetrievedFragment(
                        text=record.texte_fragment,
                        score=round(float(record.score), 4),
                        document_id=record.id_document
                    )
                    for record in records
                ]

    async def get_embeddings_count(self) -> int:
        """Get total number of embeddings in the table."""
        async with self.db_client() as session:
            async with session.begin():
                result = await session.execute(sql_text("SELECT COUNT(*) FROM embeddings"))
                return result.scalar_one()

    async def create_index(self):
        """Create HNSW index for fast cosine similarity search."""
        async with self.db_client() as session:
            async with session.begin():
                # Check if index already exists
                check_sql = sql_text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE indexname = 'embeddings_vecteur_idx'"
                )
                exists = await session.execute(check_sql)
                if exists.scalar_one_or_none():
                    return False

                create_idx_sql = sql_text(
                    "CREATE INDEX embeddings_vecteur_idx "
                    "ON embeddings USING hnsw (vecteur vector_cosine_ops)"
                )
                await session.execute(create_idx_sql)
                await session.commit()
                self.logger.info("Created HNSW index on embeddings.vecteur")
                return True
