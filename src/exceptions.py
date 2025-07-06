"""Custom exceptions for the document search application."""


class DocumentSearchException(Exception):
    """Base exception for document search application."""
    pass


class DocumentProcessingException(DocumentSearchException):
    """Exception raised during document processing."""
    pass


class DocumentTooLargeException(DocumentProcessingException):
    """Exception raised when document exceeds size limits."""
    pass


class DocumentNotFoundError(DocumentSearchException):
    """Exception raised when document is not found."""
    pass


class TextExtractionException(DocumentProcessingException):
    """Exception raised during text extraction."""
    pass


class S3ConnectionException(DocumentSearchException):
    """Exception raised for S3 connection issues."""
    pass


class ElasticsearchConnectionException(DocumentSearchException):
    """Exception raised for Elasticsearch connection issues."""
    pass


class SearchTimeoutException(DocumentSearchException):
    """Exception raised when search operations timeout."""
    pass


class RateLimitExceededException(DocumentSearchException):
    """Exception raised when rate limit is exceeded."""
    pass


class ValidationException(DocumentSearchException):
    """Exception raised for validation errors."""
    pass 