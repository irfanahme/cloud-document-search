"""FastAPI REST API for document search service."""

import logging
from fastapi import FastAPI, HTTPException, Query, Path, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from services.document_service import DocumentService
from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Document Search API",
    description="REST API for searching documents stored in AWS S3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize document service
try:
    document_service = DocumentService()
    logger.info("Document service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize document service: {e}")
    document_service = None


# Pydantic models for request/response
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    status: int


class DocumentResult(BaseModel):
    file_name: str
    s3_key: str
    file_extension: str
    size_bytes: int
    last_modified: str
    url: str
    score: float
    highlights: Dict[str, List[str]] = {}


class SearchResponse(BaseModel):
    query: str
    total_results: int
    returned_results: int
    from_: int = Field(alias="from")
    size: int
    documents: List[DocumentResult]
    timestamp: str
    warning: Optional[str] = None

    class Config:
        populate_by_name = True


class ProcessRequest(BaseModel):
    max_workers: int = Field(default=5, ge=1, le=20)


class ProcessResponse(BaseModel):
    message: str
    results: Dict[str, Any]
    timestamp: str


class SingleDocumentResponse(BaseModel):
    message: str
    s3_key: str
    success: bool
    details: str
    processed_at: str
    timestamp: str


class StatusResponse(BaseModel):
    status: str
    service_info: Dict[str, Any]
    timestamp: str


class DeleteResponse(BaseModel):
    message: str
    s3_key: str
    timestamp: str


# Custom exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail,
            "status": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An internal error occurred",
            "status": 500
        }
    )


@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="Document Search API",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get service status information."""
    if not document_service:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        status_info = document_service.get_service_status()
        return StatusResponse(
            status="operational",
            service_info=status_info,
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )


@app.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., description="Search query"),
    size: int = Query(10, ge=1, le=100, description="Number of results to return"),
    from_: int = Query(0, ge=0, alias="from", description="Starting offset for pagination")
):
    """Search documents endpoint."""
    if not document_service:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    if not q.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )
    
    try:
        # Perform search
        results = document_service.search_documents(q, size, from_)
        
        # Convert to response model
        documents = [
            DocumentResult(
                file_name=hit['file_name'],
                s3_key=hit['s3_key'],
                file_extension=hit['file_extension'],
                size_bytes=hit['size'],
                last_modified=hit['last_modified'],
                url=hit['url'],
                score=hit['score'],
                highlights=hit.get('highlights', {})
            )
            for hit in results.get('hits', [])
        ]
        
        response = SearchResponse(
            query=q,
            total_results=results.get('total', 0),
            returned_results=len(documents),
            **{"from": from_},  # Use dict unpacking for the alias
            size=size,
            documents=documents,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Add error if present
        if 'error' in results:
            response.warning = results['error']
        
        return response
        
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.post("/documents/process", response_model=ProcessResponse)
async def process_documents(
    request: ProcessRequest = ProcessRequest(),
    background_tasks: BackgroundTasks = None
):
    """Process all documents from S3."""
    if not document_service:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        logger.info(f"Starting document processing with {request.max_workers} workers")
        results = document_service.process_all_documents(request.max_workers)
        
        return ProcessResponse(
            message="Document processing completed",
            results=results,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error processing documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )


@app.post("/documents/sync", response_model=ProcessResponse)
async def sync_documents():
    """Synchronize search index with S3."""
    if not document_service:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        logger.info("Starting document synchronization")
        results = document_service.sync_with_s3()
        
        return ProcessResponse(
            message="Synchronization completed",
            results=results,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error syncing documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Synchronization failed: {str(e)}"
        )


@app.post("/documents/{s3_key:path}", response_model=SingleDocumentResponse)
async def process_single_document(
    s3_key: str = Path(..., description="S3 key of the document to process")
):
    """Process a single document by S3 key."""
    if not document_service:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        result = document_service.process_single_document(s3_key)
        
        return SingleDocumentResponse(
            message="Document processing completed",
            s3_key=result.s3_key,
            success=result.success,
            details=result.message,
            processed_at=result.processed_at.isoformat(),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error processing document {s3_key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )


@app.delete("/documents/{s3_key:path}", response_model=DeleteResponse)
async def delete_document(
    s3_key: str = Path(..., description="S3 key of the document to delete from index")
):
    """Delete a document from the search index."""
    if not document_service:
        raise HTTPException(
            status_code=503,
            detail="Service not initialized"
        )
    
    try:
        success = document_service.delete_document(s3_key)
        
        if success:
            return DeleteResponse(
                message="Document deleted from search index",
                s3_key=s3_key,
                timestamp=datetime.utcnow().isoformat()
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Document {s3_key} not found in search index"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {s3_key}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )


# Health check for load balancers
@app.get("/health")
async def health():
    """Simple health check for load balancers."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    
    if document_service is None:
        logger.error("Cannot start server: Document service failed to initialize")
        sys.exit(1)
    
    logger.info(f"Starting Document Search API on {settings.api_host}:{settings.api_port}")
    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.api_env == 'development'),
        log_level=settings.log_level.lower()
    ) 