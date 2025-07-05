"""Main document processing service."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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


class DocumentService:
    """Main service for document processing and search operations."""
    
    def __init__(self):
        """Initialize the document service with all required components."""
        self.s3_connector = S3Connector()
        self.text_extractor = TextExtractorService()
        self.indexer = ElasticsearchIndexer()
        self._processing_lock = threading.Lock()
        
        logger.info("DocumentService initialized successfully")
    
    def process_all_documents(self, max_workers: int = 5) -> Dict[str, Any]:
        """Process all documents from S3 and index them."""
        logger.info("Starting to process all documents from S3")
        
        try:
            # Get all documents from S3
            documents = self.s3_connector.list_documents()
            
            if not documents:
                logger.info("No documents found in S3 bucket")
                return {
                    'total_documents': 0,
                    'processed': 0,
                    'failed': 0,
                    'skipped': 0,
                    'results': []
                }
            
            logger.info(f"Found {len(documents)} documents to process")
            
            # Process documents in parallel
            results = self._process_documents_parallel(documents, max_workers)
            
            # Calculate statistics
            processed = sum(1 for r in results if r.success)
            failed = len(results) - processed
            
            # Refresh the index to make documents searchable
            self.indexer.refresh_index()
            
            summary = {
                'total_documents': len(documents),
                'processed': processed,
                'failed': failed,
                'skipped': 0,
                'results': [
                    {
                        's3_key': r.s3_key,
                        'success': r.success,
                        'message': r.message,
                        'processed_at': r.processed_at.isoformat()
                    } for r in results
                ]
            }
            
            logger.info(f"Document processing completed: {processed} processed, {failed} failed")
            return summary
            
        except Exception as e:
            logger.error(f"Error in process_all_documents: {e}")
            raise
    
    def process_single_document(self, s3_key: str) -> DocumentProcessingResult:
        """Process a single document by S3 key."""
        try:
            # Check if document exists in S3
            if not self.s3_connector.document_exists(s3_key):
                return DocumentProcessingResult(
                    s3_key, False, f"Document not found in S3: {s3_key}"
                )
            
            # Get document metadata
            metadata = self.s3_connector.get_document_metadata(s3_key)
            
            # Check file size
            if metadata['size'] > settings.max_file_size_bytes:
                return DocumentProcessingResult(
                    s3_key, False, 
                    f"File too large: {metadata['size']} bytes (max: {settings.max_file_size_bytes})"
                )
            
            # Download document content
            content = self.s3_connector.get_document_content(s3_key)
            
            # Extract text
            file_name = s3_key.split('/')[-1]
            extracted_text = self.text_extractor.extract_text(content, file_name)
            
            if not extracted_text.strip():
                return DocumentProcessingResult(
                    s3_key, False, "No text could be extracted from document"
                )
            
            # Generate presigned URL
            try:
                url = self.s3_connector.get_document_url(s3_key)
            except Exception as e:
                logger.warning(f"Could not generate URL for {s3_key}: {e}")
                url = ""
            
            # Create document index
            doc_index = DocumentIndex(
                s3_key=s3_key,
                file_name=file_name,
                content=extracted_text,
                file_extension=metadata.get('content_type', '').split('/')[-1],
                size=metadata['size'],
                last_modified=metadata['last_modified'],
                etag=metadata['etag'],
                url=url
            )
            
            # Index document
            if self.indexer.index_document(doc_index):
                return DocumentProcessingResult(
                    s3_key, True, f"Successfully processed and indexed document"
                )
            else:
                return DocumentProcessingResult(
                    s3_key, False, "Failed to index document in Elasticsearch"
                )
                
        except Exception as e:
            logger.error(f"Error processing document {s3_key}: {e}")
            return DocumentProcessingResult(s3_key, False, str(e))
    
    def _process_documents_parallel(self, documents: List[S3Document], 
                                  max_workers: int) -> List[DocumentProcessingResult]:
        """Process documents in parallel using ThreadPoolExecutor."""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_doc = {
                executor.submit(self._process_s3_document, doc): doc 
                for doc in documents
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        logger.debug(f"Successfully processed: {doc.key}")
                    else:
                        logger.warning(f"Failed to process {doc.key}: {result.message}")
                        
                except Exception as e:
                    logger.error(f"Exception processing {doc.key}: {e}")
                    results.append(DocumentProcessingResult(doc.key, False, str(e)))
        
        return results
    
    def _process_s3_document(self, s3_document: S3Document) -> DocumentProcessingResult:
        """Process a single S3Document object."""
        try:
            # Check if already indexed with same etag
            existing_doc = self.indexer.get_document_by_key(s3_document.key)
            if existing_doc and existing_doc.get('etag') == s3_document.etag:
                return DocumentProcessingResult(
                    s3_document.key, True, "Document already indexed (same version)"
                )
            
            # Check file size
            if s3_document.size > settings.max_file_size_bytes:
                return DocumentProcessingResult(
                    s3_document.key, False, 
                    f"File too large: {s3_document.size} bytes"
                )
            
            # Download content
            content = self.s3_connector.get_document_content(s3_document.key)
            
            # Extract text
            extracted_text = self.text_extractor.extract_text(content, s3_document.file_name)
            
            if not extracted_text.strip():
                return DocumentProcessingResult(
                    s3_document.key, False, "No text extracted"
                )
            
            # Generate URL
            try:
                url = self.s3_connector.get_document_url(s3_document.key)
            except Exception:
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
            
            if self.indexer.index_document(doc_index):
                return DocumentProcessingResult(s3_document.key, True, "Processed successfully")
            else:
                return DocumentProcessingResult(s3_document.key, False, "Indexing failed")
                
        except Exception as e:
            return DocumentProcessingResult(s3_document.key, False, str(e))
    
    def search_documents(self, query: str, size: int = 10, from_: int = 0) -> Dict[str, Any]:
        """Search documents using the query."""
        if not query.strip():
            return {'hits': [], 'total': 0, 'query': query}
        
        try:
            results = self.indexer.search_documents(query, size, from_)
            
            # Add S3 URLs to results if not present
            for hit in results.get('hits', []):
                if not hit.get('url'):
                    try:
                        hit['url'] = self.s3_connector.get_document_url(hit['s3_key'])
                    except Exception as e:
                        logger.warning(f"Could not generate URL for {hit['s3_key']}: {e}")
                        hit['url'] = ""
            
            logger.info(f"Search query '{query}' returned {len(results.get('hits', []))} results")
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return {'hits': [], 'total': 0, 'query': query, 'error': str(e)}
    
    def delete_document(self, s3_key: str) -> bool:
        """Delete a document from both S3 and the search index."""
        try:
            # Delete from search index
            index_deleted = self.indexer.delete_document(s3_key)
            
            # Note: We don't delete from S3 as per requirements
            # The document might be deleted from S3 externally
            
            if index_deleted:
                logger.info(f"Document removed from search index: {s3_key}")
            
            return index_deleted
            
        except Exception as e:
            logger.error(f"Error deleting document {s3_key}: {e}")
            return False
    
    def sync_with_s3(self) -> Dict[str, Any]:
        """Synchronize the search index with current S3 state."""
        logger.info("Starting synchronization with S3")
        
        try:
            # Get current S3 documents
            s3_documents = {doc.key: doc for doc in self.s3_connector.list_documents()}
            s3_keys = set(s3_documents.keys())
            
            # Get current indexed documents
            # This is a simplified approach - for large indexes, use scroll API
            search_result = self.indexer.search_documents("*", size=10000)
            indexed_keys = {hit['s3_key'] for hit in search_result.get('hits', [])}
            
            # Find documents to add (in S3 but not indexed)
            to_add = s3_keys - indexed_keys
            
            # Find documents to remove (indexed but not in S3)
            to_remove = indexed_keys - s3_keys
            
            # Process additions
            added = 0
            if to_add:
                documents_to_process = [s3_documents[key] for key in to_add]
                results = self._process_documents_parallel(documents_to_process, max_workers=3)
                added = sum(1 for r in results if r.success)
            
            # Process removals
            removed = 0
            for key in to_remove:
                if self.delete_document(key):
                    removed += 1
            
            # Refresh index
            self.indexer.refresh_index()
            
            sync_result = {
                'total_s3_documents': len(s3_keys),
                'total_indexed_documents': len(indexed_keys),
                'documents_added': added,
                'documents_removed': removed,
                'sync_completed_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Sync completed: {added} added, {removed} removed")
            return sync_result
            
        except Exception as e:
            logger.error(f"Error during sync: {e}")
            raise
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status information about all services."""
        try:
            s3_info = self.s3_connector.get_bucket_info()
            index_stats = self.indexer.get_index_stats()
            
            return {
                's3_bucket': {
                    'name': s3_info['bucket_name'],
                    'region': s3_info['region'],
                    'total_objects': s3_info['total_objects'],
                    'total_size_mb': s3_info['total_size_mb']
                },
                'search_index': {
                    'name': settings.elasticsearch_index,
                    'document_count': index_stats['document_count'],
                    'index_size_mb': index_stats['index_size_mb']
                },
                'supported_extensions': settings.supported_extensions_list,
                'max_file_size_mb': settings.max_file_size_mb
            }
            
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {'error': str(e)} 