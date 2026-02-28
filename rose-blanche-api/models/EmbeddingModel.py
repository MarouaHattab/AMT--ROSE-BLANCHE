from .BaseDataModel import BaseDataModel
from .db_schemes import Embedding
from sqlalchemy.future import select
from sqlalchemy import func


class EmbeddingModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def insert_many_embeddings(self, embeddings: list, batch_size: int = 100):
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(embeddings), batch_size):
                    batch = embeddings[i:i + batch_size]
                    session.add_all(batch)
            await session.commit()
        return len(embeddings)

    async def get_embeddings_by_document(self, id_document: int):
        async with self.db_client() as session:
            result = await session.execute(
                select(Embedding).where(Embedding.id_document == id_document)
            )
            return result.scalars().all()

    async def get_total_count(self) -> int:
        async with self.db_client() as session:
            result = await session.execute(select(func.count(Embedding.id)))
            return result.scalar_one()

    async def delete_by_document(self, id_document: int):
        from sqlalchemy import delete
        async with self.db_client() as session:
            stmt = delete(Embedding).where(Embedding.id_document == id_document)
            result = await session.execute(stmt)
            await session.commit()
        return result.rowcount
