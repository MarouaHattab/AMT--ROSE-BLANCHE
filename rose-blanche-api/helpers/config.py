from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):

    APP_NAME: str = "Rose-Blanche-RAG"
    APP_VERSION: str = "1.0.0"

    # PostgreSQL
    POSTGRES_USERNAME: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_MAIN_DATABASE: str = "rose_blanche"

    # Embedding model
    EMBEDDING_MODEL_ID: str = "all-MiniLM-L6-v2"
    EMBEDDING_MODEL_SIZE: int = 384

    # Vector DB
    VECTOR_DB_DISTANCE_METHOD: str = "cosine"

    # Chunking
    DEFAULT_CHUNK_SIZE: int = 500
    DEFAULT_OVERLAP_SIZE: int = 50

    # Search
    DEFAULT_TOP_K: int = 3

    # Dataset
    DATASET_DIR: str = "/app/dataset"

    # Auto-ingest on startup
    AUTO_INGEST: bool = True

    # Celery / RabbitMQ
    CELERY_BROKER_URL: str = "amqp://guest:guest@rabbitmq:5672//"
    CELERY_RESULT_BACKEND: str = "rpc://"

    class Config:
        env_file = ".env"


def get_settings():
    return Settings()
