"""AWS S3 connector for document storage operations."""

import logging
from typing import List, Dict, Optional, Iterator
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import settings

logger = logging.getLogger(__name__)


class S3Document:
    """Represents a document stored in S3."""
    
    def __init__(self, key: str, size: int, last_modified: datetime, etag: str):
        self.key = key
        self.size = size
        self.last_modified = last_modified
        self.etag = etag
        self.file_name = key.split('/')[-1]
        self.file_extension = self.file_name.split('.')[-1].lower() if '.' in self.file_name else ''
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'key': self.key,
            'file_name': self.file_name,
            'file_extension': self.file_extension,
            'size': self.size,
            'last_modified': self.last_modified.isoformat(),
            'etag': self.etag
        }


class S3Connector:
    """Handles AWS S3 operations for document storage."""
    
    def __init__(self):
        """Initialize S3 connector with AWS credentials."""
        self.bucket_name = settings.s3_bucket_name
        self.region = settings.aws_region
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=self.region
            )
            self.s3_resource = boto3.resource(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=self.region
            )
            
            # Test connection
            self._test_connection()
            logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
            
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize S3 connector: {e}")
            raise
    
    def _test_connection(self) -> None:
        """Test S3 connection and bucket access."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise ValueError(f"Bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                raise ValueError(f"Access denied to bucket '{self.bucket_name}'")
            else:
                raise ValueError(f"Error accessing bucket: {e}")
    
    def list_documents(self, prefix: str = "", max_keys: int = 1000) -> List[S3Document]:
        """List all documents in the S3 bucket."""
        documents = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Filter by supported extensions
                        file_extension = obj['Key'].split('.')[-1].lower() if '.' in obj['Key'] else ''
                        if f".{file_extension}" in settings.supported_extensions_list:
                            document = S3Document(
                                key=obj['Key'],
                                size=obj['Size'],
                                last_modified=obj['LastModified'],
                                etag=obj['ETag'].strip('"')
                            )
                            documents.append(document)
            
            logger.info(f"Found {len(documents)} supported documents in S3")
            return documents
            
        except ClientError as e:
            logger.error(f"Error listing documents: {e}")
            raise
    
    def get_document_content(self, document_key: str) -> bytes:
        """Download document content from S3."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=document_key
            )
            content = response['Body'].read()
            logger.debug(f"Downloaded document: {document_key} ({len(content)} bytes)")
            return content
            
        except ClientError as e:
            logger.error(f"Error downloading document {document_key}: {e}")
            raise
    
    def get_document_stream(self, document_key: str):
        """Get document content as a stream for efficient processing."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=document_key
            )
            return response['Body']
            
        except ClientError as e:
            logger.error(f"Error getting document stream {document_key}: {e}")
            raise
    
    def get_document_content_efficient(self, document_key: str, max_memory_size: int = 10 * 1024 * 1024) -> bytes:
        """Download document content with memory optimization.
        
        Args:
            document_key: S3 key of the document
            max_memory_size: Maximum size to load into memory (default: 10MB)
            
        Returns:
            Document content as bytes
            
        Raises:
            ValueError: If file is too large for memory processing
        """
        try:
            # Get metadata first to check file size
            metadata = self.get_document_metadata(document_key)
            file_size = metadata['size']
            
            # If file is too large, recommend streaming
            if file_size > max_memory_size:
                raise ValueError(
                    f"File {document_key} is too large ({file_size} bytes) for memory processing. "
                    f"Use get_document_stream() instead."
                )
            
            # File is small enough, load into memory
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=document_key
            )
            content = response['Body'].read()
            logger.debug(f"Downloaded document: {document_key} ({len(content)} bytes)")
            return content
            
        except ClientError as e:
            logger.error(f"Error downloading document {document_key}: {e}")
            raise
    
    def get_document_metadata(self, document_key: str) -> Dict:
        """Get document metadata from S3."""
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=document_key
            )
            
            return {
                'key': document_key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'etag': response['ETag'].strip('"'),
                'content_type': response.get('ContentType', ''),
                'metadata': response.get('Metadata', {})
            }
            
        except ClientError as e:
            logger.error(f"Error getting metadata for {document_key}: {e}")
            raise
    
    def document_exists(self, document_key: str) -> bool:
        """Check if a document exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=document_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def get_document_url(self, document_key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for document access."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': document_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL for {document_key}: {e}")
            raise
    
    def get_documents_modified_after(self, timestamp: datetime) -> List[S3Document]:
        """Get documents modified after a specific timestamp."""
        all_documents = self.list_documents()
        return [doc for doc in all_documents if doc.last_modified > timestamp]
    
    def get_bucket_info(self) -> Dict:
        """Get information about the S3 bucket."""
        try:
            # Get bucket location
            location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)
            
            # Count objects and total size
            total_objects = 0
            total_size = 0
            
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name):
                if 'Contents' in page:
                    total_objects += len(page['Contents'])
                    total_size += sum(obj['Size'] for obj in page['Contents'])
            
            return {
                'bucket_name': self.bucket_name,
                'region': location['LocationConstraint'] or 'us-east-1',
                'total_objects': total_objects,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
            
        except ClientError as e:
            logger.error(f"Error getting bucket info: {e}")
            raise 