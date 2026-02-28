from enum import Enum


class ResponseSignal(Enum):
    FILE_VALIDATED_SUCCESS = "file_validate_successfully"
    FILE_TYPE_NOT_SUPPORTED = "file_type_not_supported"
    PROCESSING_SUCCESS = "processing_success"
    PROCESSING_FAILED = "processing_failed"
    INGESTION_SUCCESS = "ingestion_success"
    INGESTION_FAILED = "ingestion_failed"
    SEARCH_SUCCESS = "search_success"
    SEARCH_ERROR = "search_error"
    SEARCH_NO_RESULTS = "search_no_results"
    DOCUMENTS_LISTED = "documents_listed"
    DOCUMENT_NOT_FOUND = "document_not_found"
    EMBEDDINGS_COUNT = "embeddings_count"
    DATABASE_READY = "database_ready"
    DATABASE_ERROR = "database_error"
