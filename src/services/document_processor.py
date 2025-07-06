"""Document processing service focused on processing individual documents."""

import logging
from typing import Dict, Any
from datetime import datetime

from connectors.s3_connector import S3Connector, S3Document
from extractors.text_extractor import TextExtractorService
from indexer.elasticsearch_indexer import ElasticsearchIndexer, DocumentIndex
from config import settings

logger = logging.getLogger(__name__)


class DocumentProcessingResult:
    """Result of document processing operation."""
    
    def __init__(self, s3_key: str, success: bool, message: str = ""):
        self.s3_key = s3_key
        self.success = success
        self.message = message
        self.processed_at = datetime.utcnow()


class DocumentProcessor:
    """Handles processing of individual documents."""
    
    def __init__(self, s3_connector: S3Connector, text_extractor: TextExtractorService, 
                 indexer: ElasticsearchIndexer):
        """Initialize processor with required components."""
        self.s3_connector = s3_connector
        self.text_extractor = text_extractor
        self.indexer = indexer
        logger.info("DocumentProcessor initialized")
    
    def process_document(self, s3_document: S3Document) -> DocumentProcessingResult:
        """Process a single S3Document object.
        
        Args:
            s3_document: The document to process
            
        Returns:
            DocumentProcessingResult: Result of the processing operation
        """
        try:
            # Check if already indexed with same etag
            existing_doc = self.indexer.get_document_by_key(s3_document.key)
            if existing_doc and existing_doc.get('etag') == s3_document.etag:
                return DocumentProcessingResult(
                    s3_document.key, True, "Document already indexed (same version)"
                )
            
            # Validate file size
            if s3_document.size > settings.max_file_size_bytes:
                return DocumentProcessingResult(
                    s3_document.key, False, 
                    f"File too large: {s3_document.size} bytes (max: {settings.max_file_size_bytes})"
                )
            
            # Download content efficiently
            try:
                content = self.s3_connector.get_document_content_efficient(s3_document.key)
            except ValueError as e:
                return DocumentProcessingResult(
                    s3_document.key, False, f"File too large for processing: {str(e)}"
                )
            
            # Extract text
            extracted_text = self.text_extractor.extract_text(content, s3_document.file_name)
            
            if not extracted_text.strip():
                return DocumentProcessingResult(
                    s3_document.key, False, "No text extracted from document"
                )
            
            # Generate URL
            try:
                url = self.s3_connector.get_document_url(s3_document.key)
            except Exception as e:
                logger.warning(f"Could not generate URL for {s3_document.key}: {e}")
                url = ""
            
            # Create and index document
            doc_index = DocumentIndex(
                s3_key=s3_document.key,
                file_name=s3_document.file_name,
                content=extracted_text,
                file_extension=s3_document.file_extension,
                size=s3_document.size,
                last_modified=s3_document.last_modified.isoformat(),
                etag=s3_document.etag,
                url=url
            )
            
            # Index document
            if self.indexer.index_document(doc_index):
                return DocumentProcessingResult(
                    s3_document.key, True, "Successfully processed and indexed document"
                )
            else:
                return DocumentProcessingResult(
                    s3_document.key, False, "Failed to index document in Elasticsearch"
                )
                
        except Exception as e:
            logger.error(f"Error processing document {s3_document.key}: {e}")
            return DocumentProcessingResult(s3_document.key, False, str(e))
    
    def process_document_by_key(self, s3_key: str) -> DocumentProcessingResult:
        """Process a single document by S3 key.
        
        Args:
            s3_key: The S3 key of the document to process
            
        Returns:
            DocumentProcessingResult: Result of the processing operation
        """
        try:
            # Check if document exists in S3
            if not self.s3_connector.document_exists(s3_key):
                return DocumentProcessingResult(
                    s3_key, False, f"Document not found in S3: {s3_key}"
                )
            
            # Get document metadata
            metadata = self.s3_connector.get_document_metadata(s3_key)
            
            # Create S3Document object
            s3_document = S3Document(
                key=s3_key,
                size=metadata['size'],
                last_modified=datetime.fromisoformat(metadata['last_modified'].replace('Z', '+00:00')),
                etag=metadata['etag']
            )
            
            return self.process_document(s3_document)
            
        except Exception as e:
            logger.error(f"Error processing document {s3_key}: {e}")
            return DocumentProcessingResult(s3_key, False, str(e)) 