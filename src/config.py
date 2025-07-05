"""Configuration management for the document search application."""

import os
from typing import List
from pydantic import BaseSettings, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings using Pydantic BaseSettings."""
    
    # AWS Configuration
    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    s3_bucket_name: str = Field(..., env="S3_BUCKET_NAME")
    
    # Elasticsearch Configuration
    elasticsearch_host: str = Field(default="localhost", env="ELASTICSEARCH_HOST")
    elasticsearch_port: int = Field(default=9200, env="ELASTICSEARCH_PORT")
    elasticsearch_index: str = Field(default="documents", env="ELASTICSEARCH_INDEX")
    elasticsearch_user: str = Field(default="", env="ELASTICSEARCH_USER")
    elasticsearch_password: str = Field(default="", env="ELASTICSEARCH_PASSWORD")
    
    # Application Configuration
    api_env: str = Field(default="development", env="API_ENV")
    api_port: int = Field(default=5000, env="API_PORT")
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Document Processing Configuration
    max_file_size_mb: int = Field(default=100, env="MAX_FILE_SIZE_MB")
    supported_extensions: str = Field(
        default=".txt,.csv,.pdf,.png,.jpg,.jpeg,.docx,.xlsx",
        env="SUPPORTED_EXTENSIONS"
    )
    tesseract_path: str = Field(default="/usr/bin/tesseract", env="TESSERACT_PATH")
    
    @property
    def supported_extensions_list(self) -> List[str]:
        """Convert comma-separated extensions to list."""
        return [ext.strip() for ext in self.supported_extensions.split(",")]
    
    @property
    def elasticsearch_url(self) -> str:
        """Get Elasticsearch URL."""
        return f"http://{self.elasticsearch_host}:{self.elasticsearch_port}"
    
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings() 