from .base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
import uuid


class Document(SQLAlchemyBase):

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    nom_fichier = Column(String(500), nullable=False, unique=True)
    titre = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    embeddings = relationship("Embedding", back_populates="document")


class Embedding(SQLAlchemyBase):
    """
    Stores text fragments and their vector embeddings.
    Matches the challenge requirement:
      - id (PK)
      - id_document (int, FK → documents.id)
      - texte_fragment (text)
      - vecteur (VECTOR(384))
    """
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_document = Column(Integer, ForeignKey("documents.id"), nullable=False)
    texte_fragment = Column(Text, nullable=False)
    vecteur = Column(Vector(384), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    document = relationship("Document", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_id_document", "id_document"),
    )


class RetrievedFragment(BaseModel):
    """Pydantic model for search results."""
    text: str
    score: float
    document_id: int
