"""Basic tests for the Document Search FastAPI."""

import pytest
import json
from unittest.mock import Mock, patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi.testclient import TestClient
from api.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'Document Search API'


def test_api_documentation(client):
    """Test API documentation endpoint (OpenAPI docs)."""
    response = client.get('/docs')
    assert response.status_code == 200
    # FastAPI automatically generates OpenAPI docs


def test_openapi_schema(client):
    """Test OpenAPI schema endpoint."""
    response = client.get('/openapi.json')
    assert response.status_code == 200
    data = response.json()
    assert 'openapi' in data
    assert data['info']['title'] == 'Document Search API'


def test_search_missing_query(client):
    """Test search endpoint with missing query parameter."""
    response = client.get('/search')
    assert response.status_code == 422  # FastAPI returns 422 for validation errors
    data = response.json()
    assert 'detail' in data


def test_search_invalid_size(client):
    """Test search endpoint with invalid size parameter."""
    response = client.get('/search?q=test&size=0')
    assert response.status_code == 422  # Validation error
    data = response.json()
    assert 'detail' in data


def test_search_invalid_from(client):
    """Test search endpoint with invalid from parameter."""
    response = client.get('/search?q=test&from=-1')
    assert response.status_code == 422  # Validation error
    data = response.json()
    assert 'detail' in data


@patch('api.app.document_service')
def test_search_success(mock_service, client):
    """Test successful search."""
    # Mock the document service
    mock_service.search_documents.return_value = {
        'hits': [
            {
                'file_name': 'test.txt',
                's3_key': 'test.txt',
                'file_extension': 'txt',
                'size': 100,
                'last_modified': '2023-01-01T00:00:00',
                'url': 'http://example.com/test.txt',
                'score': 1.0,
                'highlights': {}
            }
        ],
        'total': 1
    }
    
    response = client.get('/search?q=test')
    assert response.status_code == 200
    data = response.json()
    assert data['query'] == 'test'
    assert data['total_results'] == 1
    assert len(data['documents']) == 1
    assert data['documents'][0]['file_name'] == 'test.txt'


def test_not_found(client):
    """Test 404 error handling."""
    response = client.get('/nonexistent')
    assert response.status_code == 404
    data = response.json()
    assert 'detail' in data


@patch('api.app.document_service')
def test_process_documents(mock_service, client):
    """Test process documents endpoint."""
    mock_service.process_all_documents.return_value = {
        'total_documents': 5,
        'processed': 5,
        'failed': 0,
        'results': []
    }
    
    response = client.post('/documents/process', json={'max_workers': 3})
    assert response.status_code == 200
    data = response.json()
    assert data['message'] == 'Document processing completed'
    assert 'results' in data


@patch('api.app.document_service')  
def test_sync_documents(mock_service, client):
    """Test sync documents endpoint."""
    mock_service.sync_with_s3.return_value = {
        'total_s3_documents': 10,
        'total_indexed_documents': 8,
        'documents_added': 2,
        'documents_removed': 0
    }
    
    response = client.post('/documents/sync')
    assert response.status_code == 200
    data = response.json()
    assert data['message'] == 'Synchronization completed'
    assert 'results' in data


def test_health_endpoint(client):
    """Test additional health endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'


if __name__ == '__main__':
    pytest.main([__file__]) 