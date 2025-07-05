"""Main application entry point for Document Search FastAPI."""

import os
import sys
import uvicorn

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.app import app
from src.config import settings

if __name__ == '__main__':
    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.api_env == 'development'),
        log_level=settings.log_level.lower()
    ) 