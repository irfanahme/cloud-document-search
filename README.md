# Document Search Application

A comprehensive cloud document search service that enables full-text search across documents stored in AWS S3. The application extracts text from various document formats (PDF, Word, Excel, CSV, images) using OCR and indexes them in Elasticsearch for fast, powerful search capabilities. Built with FastAPI for high performance and automatic API documentation.

## 🏗️ High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Interface │────│   REST API       │────│  Search Service │
│   (CLI/Web)      │    │   (FastAPI)      │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                         │
                                │                         ▼
                        ┌──────────────┐         ┌─────────────────┐
                        │  Document    │         │  Elasticsearch  │
                        │  Processor   │         │     Index       │
                        └──────────────┘         └─────────────────┘
                                │
                                ▼
                  ┌─────────────────────────────────┐
                  │      Text Extractors            │
                  │  ┌─────┐ ┌─────┐ ┌─────┐       │
                  │  │ PDF │ │ OCR │ │ CSV │  ...  │
                  │  └─────┘ └─────┘ └─────┘       │
                  └─────────────────────────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │   AWS S3     │
                        │   Storage    │
                        └──────────────┘
```

## ✨ Features

- **Multi-format Support**: Extract text from PDF, Word (.docx), Excel (.xlsx), CSV, TXT, and image files
- **OCR Capabilities**: Extract text from images using Tesseract OCR
- **AWS S3 Integration**: Seamlessly connect to your S3 bucket
- **Full-text Search**: Powered by Elasticsearch with relevance scoring
- **FastAPI REST API**: High-performance async API with automatic OpenAPI documentation
- **Interactive Documentation**: Built-in Swagger UI and ReDoc for API exploration
- **CLI Interface**: Rich command-line interface for easy interaction
- **Docker Support**: Containerized deployment with Docker Compose
- **Parallel Processing**: Multi-threaded document processing
- **Real-time Sync**: Synchronize index with S3 bucket changes

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose (for containerized deployment)
- AWS account with S3 access
- Elasticsearch 8.x (provided via Docker Compose)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd document-search-app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Copy the configuration template and update with your settings:

```bash
cp config.env.example .env
```

Edit `.env` file with your AWS credentials and configuration:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-document-bucket

# Elasticsearch Configuration
ELASTICSEARCH_HOST=localhost
ELASTICSEARCH_PORT=9200
ELASTICSEARCH_INDEX=documents

# Application Configuration
API_ENV=development
API_PORT=5000
LOG_LEVEL=INFO
```

### 3. Start Services

#### Option A: Docker Compose (Recommended)

```bash
# Start Elasticsearch and the API
docker-compose up -d

# With Kibana for visualization
docker-compose --profile with-kibana up -d
```

#### Option B: Local Development

```bash
# Start Elasticsearch (separate terminal)
docker run -d -p 9200:9200 -e "discovery.type=single-node" -e "xpack.security.enabled=false" docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# Start the FastAPI application
uvicorn src.api.app:app --host 0.0.0.0 --port 5000 --reload
```

### 4. Process Documents

```bash
# Using CLI
python cli.py process

# Using API
curl -X POST http://localhost:5000/documents/process
```

### 5. Search Documents

```bash
# Using CLI
python cli.py search "your search term"

# Using API
curl "http://localhost:5000/search?q=your+search+term"
```

## 📖 API Documentation

### Base URL
- Development: `http://localhost:5000`
- Production: Your deployed URL

### Interactive Documentation
- **Swagger UI**: `http://localhost:5000/docs`
- **ReDoc**: `http://localhost:5000/redoc`
- **OpenAPI Schema**: `http://localhost:5000/openapi.json`

### Endpoints

#### Health Check
```http
GET /
```
Returns service health status.

#### Search Documents
```http
GET /search?q={query}&size={size}&from={from}
```

**Parameters:**
- `q` (required): Search query
- `size` (optional): Number of results (default: 10, max: 100)
- `from` (optional): Starting offset for pagination (default: 0)

**Example:**
```bash
curl "http://localhost:5000/search?q=important+document&size=5"
```

**Response:**
```json
{
  "query": "important document",
  "total_results": 25,
  "returned_results": 5,
  "documents": [
    {
      "file_name": "report.pdf",
      "s3_key": "documents/report.pdf",
      "file_extension": "pdf",
      "size_bytes": 1024000,
      "last_modified": "2023-12-01T10:30:00",
      "url": "https://presigned-url...",
      "score": 2.5,
      "highlights": {
        "content": ["This is an <em>important document</em>..."]
      }
    }
  ]
}
```

#### Process All Documents
```http
POST /documents/process
```

**Body:**
```json
{
  "max_workers": 5
}
```

#### Synchronize with S3
```http
POST /documents/sync
```

#### Process Single Document
```http
POST /documents/{s3_key}
```

#### Delete Document from Index
```http
DELETE /documents/{s3_key}
```

#### Service Status
```http
GET /status
```

## 💻 CLI Usage

The CLI provides a rich interface for interacting with the service:

### Installation
```bash
pip install -r requirements.txt
```

### Commands

#### Search Documents
```bash
python cli.py search "search term"
python cli.py search "email address" --size 20 --format json
python cli.py search "quarterly report" --format table
```

#### Process All Documents
```bash
python cli.py process
python cli.py process --workers 10
```

#### Synchronize with S3
```bash
python cli.py sync
```

#### Service Status
```bash
python cli.py status
```

#### Process Single Document
```bash
python cli.py process-single "path/to/document.pdf"
```

#### Delete Document
```bash
python cli.py delete "path/to/document.pdf"
```

### CLI Options
- `--api-url`: Specify API URL (default: http://localhost:5000)
- `--format`: Output format for search results (table, json, simple)
- `--size`: Number of results to return
- `--workers`: Number of parallel processing workers

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS Access Key | Required |
| `AWS_SECRET_ACCESS_KEY` | AWS Secret Key | Required |
| `AWS_REGION` | AWS Region | us-east-1 |
| `S3_BUCKET_NAME` | S3 Bucket Name | Required |
| `ELASTICSEARCH_HOST` | Elasticsearch Host | localhost |
| `ELASTICSEARCH_PORT` | Elasticsearch Port | 9200 |
| `ELASTICSEARCH_INDEX` | Index Name | documents |
| `API_PORT` | API Port | 5000 |
| `LOG_LEVEL` | Logging Level | INFO |
| `MAX_FILE_SIZE_MB` | Max File Size | 100 |
| `TESSERACT_PATH` | Tesseract Binary Path | /usr/bin/tesseract |

### Supported File Formats

- **Text Files**: .txt, .csv, .log, .md
- **PDF Files**: .pdf
- **Microsoft Office**: .docx, .xlsx
- **Images**: .png, .jpg, .jpeg, .gif, .bmp, .tiff

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t document-search-app .
```

### Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f document-search-api

# Stop services
docker-compose down

# With Kibana for Elasticsearch visualization
docker-compose --profile with-kibana up -d
```

### Environment File for Docker
Create `.env` file for Docker Compose:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket
```

## 📊 Monitoring

### Application Logs
```bash
# View API logs
docker-compose logs -f document-search-api

# View Elasticsearch logs
docker-compose logs -f elasticsearch
```

### Health Checks
- API Health: `http://localhost:5000/health`
- API Status: `http://localhost:5000/`
- API Documentation: `http://localhost:5000/docs`
- Elasticsearch: `http://localhost:9200/_cluster/health`
- Kibana (if enabled): `http://localhost:5601`

### Metrics and Status
```bash
# CLI status
python cli.py status

# API status
curl http://localhost:5000/status
```

## 🔍 Usage Examples

### Example 1: Email Search
```bash
# Find all documents containing email addresses
python cli.py search "@gmail.com" --size 50
```

### Example 2: Date Range Content
```bash
# Search for quarterly reports
curl "http://localhost:5000/search?q=quarterly+report+2023"
```

### Example 3: File Type Filtering
Since the API returns file extensions, you can filter client-side:
```bash
# Search for PDFs containing "contract"
python cli.py search "contract" --format json | jq '.documents[] | select(.file_extension == "pdf")'
```

## 🛠️ Development

### Project Structure
```
document-search-app/
├── src/
│   ├── api/                 # REST API layer
│   ├── cli/                 # Command line interface
│   ├── connectors/          # Cloud storage connectors
│   ├── extractors/          # Text extraction services
│   ├── indexer/            # Search indexing services
│   └── services/           # Business logic services
├── tests/                  # Test suite
├── docs/                   # Documentation
├── scripts/                # Utility scripts
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container definition
├── docker-compose.yml     # Multi-service deployment
└── README.md              # This file
```

### Adding New File Types

1. Create a new extractor class in `src/extractors/text_extractor.py`
2. Implement the `BaseExtractor` interface
3. Add the extractor to `TextExtractorService`
4. Update supported extensions in configuration

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## 🚨 Troubleshooting

### Common Issues

#### 1. Elasticsearch Connection Error
```bash
# Check if Elasticsearch is running
curl http://localhost:9200

# Start Elasticsearch
docker-compose up elasticsearch -d
```

#### 2. AWS Credentials Error
```bash
# Verify credentials
aws s3 ls s3://your-bucket-name

# Check environment variables
echo $AWS_ACCESS_KEY_ID
```

#### 3. OCR Not Working
```bash
# Install Tesseract (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-eng

# macOS
brew install tesseract

# Verify installation
tesseract --version
```

#### 4. Large File Processing
- Increase `MAX_FILE_SIZE_MB` in configuration
- Monitor memory usage during processing
- Consider processing large files separately

### Performance Tuning

1. **Elasticsearch**: Increase heap size for large datasets
2. **Processing**: Adjust `max_workers` based on system resources
3. **Search**: Use pagination for large result sets
4. **Indexing**: Batch process documents during off-peak hours

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the API documentation
3. Check existing issues in the repository
4. Create a new issue with detailed information

## 🔮 Future Enhancements

- Support for more file formats (PowerPoint, OpenDocument)
- Advanced search features (filters, facets)
- Real-time document change detection
- Multi-language OCR support
- Search result caching
- Analytics and usage metrics
- Web UI for search interface 