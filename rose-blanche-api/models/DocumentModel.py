from .BaseDataModel import BaseDataModel
from .db_schemes import Document
from sqlalchemy.future import select
from sqlalchemy import func


class DocumentModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def create_document(self, document: Document) -> Document:
        async with self.db_client() as session:
            async with session.begin():
                session.add(document)
            await session.commit()
            await session.refresh(document)
        return document

    async def get_document_by_filename(self, nom_fichier: str):
        async with self.db_client() as session:
            result = await session.execute(
                select(Document).where(Document.nom_fichier == nom_fichier)
            )
            return result.scalar_one_or_none()

    async def get_all_documents(self):
        async with self.db_client() as session:
            result = await session.execute(select(Document))
            return result.scalars().all()

    async def get_document_count(self) -> int:
        async with self.db_client() as session:
            result = await session.execute(select(func.count(Document.id)))
            return result.scalar_one()
