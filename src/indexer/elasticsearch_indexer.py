"""Elasticsearch indexer for document search and storage."""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ConnectionError, NotFoundError, RequestError
from config import settings
from connectors.s3_connector import S3Document

logger = logging.getLogger(__name__)


class DocumentIndex:
    """Represents a document in the search index."""
    
    def __init__(self, s3_key: str, file_name: str, content: str, 
                 file_extension: str, size: int, last_modified: str, 
                 etag: str, url: str = ""):
        self.s3_key = s3_key
        self.file_name = file_name
        self.content = content
        self.file_extension = file_extension
        self.size = size
        self.last_modified = last_modified
        self.etag = etag
        self.url = url
        self.indexed_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Elasticsearch indexing."""
        return {
            's3_key': self.s3_key,
            'file_name': self.file_name,
            'content': self.content,
            'file_extension': self.file_extension,
            'size': self.size,
            'last_modified': self.last_modified,
            'etag': self.etag,
            'url': self.url,
            'indexed_at': self.indexed_at
        }


class ElasticsearchIndexer:
    """Handles Elasticsearch operations for document indexing and searching."""
    
    def __init__(self):
        """Initialize Elasticsearch connection."""
        self.index_name = settings.elasticsearch_index
        
        # Configure Elasticsearch client
        es_config = {
            'hosts': [settings.elasticsearch_url],
            'request_timeout': 30,
            'max_retries': 3,
            'retry_on_timeout': True
        }
        
        # Add authentication if credentials are provided
        if settings.elasticsearch_user and settings.elasticsearch_password:
            es_config['basic_auth'] = (
                settings.elasticsearch_user,
                settings.elasticsearch_password
            )
        
        self.es = Elasticsearch(**es_config)
        
        try:
            # Test connection
            if not self.es.ping():
                raise ConnectionError("Unable to connect to Elasticsearch")
            
            logger.info(f"Connected to Elasticsearch at {settings.elasticsearch_url}")
            
            # Create index if it doesn't exist
            self._create_index_if_not_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Elasticsearch: {e}")
            raise
    
    def _create_index_if_not_exists(self) -> None:
        """Create the documents index if it doesn't exist."""
        if not self.es.indices.exists(index=self.index_name):
            index_mapping = {
                "mappings": {
                    "properties": {
                        "s3_key": {
                            "type": "keyword"
                        },
                        "file_name": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "keyword": {
                                    "type": "keyword",
                                    "ignore_above": 256
                                }
                            }
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "file_extension": {
                            "type": "keyword"
                        },
                        "size": {
                            "type": "long"
                        },
                        "last_modified": {
                            "type": "date"
                        },
                        "etag": {
                            "type": "keyword"
                        },
                        "url": {
                            "type": "keyword"
                        },
                        "indexed_at": {
                            "type": "date"
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "analysis": {
                        "analyzer": {
                            "default": {
                                "type": "standard",
                                "stopwords": "_english_"
                            }
                        }
                    }
                }
            }
            
            self.es.indices.create(index=self.index_name, body=index_mapping)
            logger.info(f"Created Elasticsearch index: {self.index_name}")
        else:
            logger.info(f"Elasticsearch index already exists: {self.index_name}")
    
    def index_document(self, document: DocumentIndex) -> bool:
        """Index a single document."""
        try:
            response = self.es.index(
                index=self.index_name,
                id=document.s3_key,  # Use S3 key as document ID
                body=document.to_dict()
            )
            
            logger.debug(f"Indexed document: {document.file_name} with result: {response['result']}")
            return response['result'] in ['created', 'updated']
            
        except Exception as e:
            logger.error(f"Error indexing document {document.file_name}: {e}")
            return False
    
    def bulk_index_documents(self, documents: List[DocumentIndex]) -> Dict[str, int]:
        """Bulk index multiple documents."""
        if not documents:
            return {'successful': 0, 'failed': 0}
        
        # Prepare bulk actions
        actions = []
        for doc in documents:
            action = {
                '_index': self.index_name,
                '_id': doc.s3_key,
                '_source': doc.to_dict()
            }
            actions.append(action)
        
        try:
            # Perform bulk indexing
            success_count, failed_items = helpers.bulk(
                self.es,
                actions,
                chunk_size=100,
                request_timeout=60
            )
            
            failed_count = len(failed_items) if failed_items else 0
            
            logger.info(f"Bulk indexing completed: {success_count} successful, {failed_count} failed")
            
            return {
                'successful': success_count,
                'failed': failed_count
            }
            
        except Exception as e:
            logger.error(f"Error in bulk indexing: {e}")
            return {'successful': 0, 'failed': len(documents)}
    
    def search_documents(self, query: str, size: int = 10, from_: int = 0) -> Dict[str, Any]:
        """Search documents by content or filename."""
        if not query.strip():
            return {'hits': [], 'total': 0}
        
        search_body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content^2", "file_name^1.5"],  # Boost content matches
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "highlight": {
                "fields": {
                    "content": {
                        "fragment_size": 150,
                        "number_of_fragments": 3
                    },
                    "file_name": {}
                }
            },
            "size": size,
            "from": from_,
            "sort": [
                {"_score": {"order": "desc"}},
                {"last_modified": {"order": "desc"}}
            ]
        }
        
        try:
            response = self.es.search(
                index=self.index_name,
                body=search_body
            )
            
            hits = []
            for hit in response['hits']['hits']:
                result = {
                    'score': hit['_score'],
                    's3_key': hit['_source']['s3_key'],
                    'file_name': hit['_source']['file_name'],
                    'file_extension': hit['_source']['file_extension'],
                    'size': hit['_source']['size'],
                    'last_modified': hit['_source']['last_modified'],
                    'url': hit['_source'].get('url', ''),
                    'highlights': hit.get('highlight', {})
                }
                hits.append(result)
            
            total = response['hits']['total']['value'] if isinstance(response['hits']['total'], dict) else response['hits']['total']
            
            return {
                'hits': hits,
                'total': total,
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return {'hits': [], 'total': 0, 'error': str(e)}
    
    def delete_document(self, s3_key: str) -> bool:
        """Delete a document from the index."""
        try:
            response = self.es.delete(
                index=self.index_name,
                id=s3_key
            )
            logger.info(f"Deleted document from index: {s3_key}")
            return response['result'] == 'deleted'
            
        except NotFoundError:
            logger.warning(f"Document not found in index: {s3_key}")
            return False
        except Exception as e:
            logger.error(f"Error deleting document {s3_key}: {e}")
            return False
    
    def document_exists_in_index(self, s3_key: str) -> bool:
        """Check if a document exists in the index."""
        try:
            return self.es.exists(index=self.index_name, id=s3_key)
        except Exception as e:
            logger.error(f"Error checking document existence {s3_key}: {e}")
            return False
    
    def get_document_by_key(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """Get a document from the index by S3 key."""
        try:
            response = self.es.get(index=self.index_name, id=s3_key)
            return response['_source']
        except NotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error getting document {s3_key}: {e}")
            return None
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the index."""
        try:
            stats = self.es.indices.stats(index=self.index_name)
            count_response = self.es.count(index=self.index_name)
            
            index_stats = stats['indices'][self.index_name]
            
            return {
                'document_count': count_response['count'],
                'index_size_bytes': index_stats['total']['store']['size_in_bytes'],
                'index_size_mb': round(index_stats['total']['store']['size_in_bytes'] / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {'document_count': 0, 'index_size_bytes': 0, 'index_size_mb': 0}
    
    def refresh_index(self) -> None:
        """Refresh the index to make recent changes available for search."""
        try:
            self.es.indices.refresh(index=self.index_name)
            logger.debug(f"Refreshed index: {self.index_name}")
        except Exception as e:
            logger.error(f"Error refreshing index: {e}")
    
    def clear_index(self) -> bool:
        """Clear all documents from the index."""
        try:
            response = self.es.delete_by_query(
                index=self.index_name,
                body={"query": {"match_all": {}}}
            )
            deleted_count = response.get('deleted', 0)
            logger.info(f"Cleared {deleted_count} documents from index")
            return True
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            return False 