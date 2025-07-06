"""Main document service orchestrating all document operations."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from connectors.s3_connector import S3Connector, S3Document
from extractors.text_extractor import TextExtractorService
from indexer.elasticsearch_indexer import ElasticsearchIndexer, DocumentIndex
from config import settings
from exceptions import DocumentSearchException, DocumentNotFoundError
from .document_processor import DocumentProcessor, DocumentProcessingResult
from .batch_processor import BatchProcessor

logger = logging.getLogger(__name__)


class DocumentService:
    """Main service orchestrating document operations."""
    
    def __init__(self):
        """Initialize the document service with all required components."""
        # Initialize core components
        self.s3_connector = S3Connector()
        self.text_extractor = TextExtractorService()
        self.indexer = ElasticsearchIndexer()
        
        # Initialize specialized processors
        self.document_processor = DocumentProcessor(
            self.s3_connector, self.text_extractor, self.indexer
        )
        self.batch_processor = BatchProcessor(self.document_processor)
        
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
            
            # Process documents using batch processor
            results = self.batch_processor.process_documents_batch(documents, max_workers)
            
            # Refresh the index to make documents searchable
            self.indexer.refresh_index()
            
            logger.info(f"Document processing completed: {results['processed']} processed, {results['failed']} failed")
            return results
            
        except Exception as e:
            logger.error(f"Error in process_all_documents: {e}")
            raise DocumentSearchException(f"Failed to process documents: {str(e)}")
    
    def process_single_document(self, s3_key: str) -> DocumentProcessingResult:
        """Process a single document by S3 key."""
        try:
            return self.document_processor.process_document_by_key(s3_key)
        except Exception as e:
            logger.error(f"Error processing document {s3_key}: {e}")
            raise DocumentSearchException(f"Failed to process document {s3_key}: {str(e)}")
    

    
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