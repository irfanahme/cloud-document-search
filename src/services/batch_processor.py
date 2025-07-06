"""Batch processing service for handling multiple documents efficiently."""

import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from connectors.s3_connector import S3Document
from .document_processor import DocumentProcessor, DocumentProcessingResult

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Handles batch processing of multiple documents."""
    
    def __init__(self, document_processor: DocumentProcessor):
        """Initialize batch processor."""
        self.document_processor = document_processor
        self._processing_lock = threading.Lock()
        logger.info("BatchProcessor initialized")
    
    def process_documents_batch(self, documents: List[S3Document], 
                               max_workers: int = 5) -> Dict[str, Any]:
        """Process multiple documents in parallel.
        
        Args:
            documents: List of S3Document objects to process
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dict containing processing results and statistics
        """
        if not documents:
            return {
                'total_documents': 0,
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'results': []
            }
        
        logger.info(f"Starting batch processing of {len(documents)} documents with {max_workers} workers")
        
        with self._processing_lock:
            results = self._process_documents_parallel(documents, max_workers)
            
            # Calculate statistics
            processed = sum(1 for r in results if r.success)
            failed = len(results) - processed
            
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
            
            logger.info(f"Batch processing completed: {processed} processed, {failed} failed")
            return summary
    
    def _process_documents_parallel(self, documents: List[S3Document], 
                                  max_workers: int) -> List[DocumentProcessingResult]:
        """Process documents in parallel using ThreadPoolExecutor."""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_doc = {
                executor.submit(self.document_processor.process_document, doc): doc 
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