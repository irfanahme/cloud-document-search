#!/usr/bin/env python3
"""Setup script for Document Search Application."""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, description=""):
    """Run a shell command and handle errors."""
    print(f"Running: {description or command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error running command: {e}")
        return False

def check_requirements():
    """Check if required tools are installed."""
    print("Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("Error: Python 3.9+ is required")
        return False
    
    # Check Docker
    if not run_command("docker --version", "Checking Docker"):
        print("Warning: Docker not found. You'll need to install Docker for containerized deployment.")
    
    # Check Docker Compose
    if not run_command("docker-compose --version", "Checking Docker Compose"):
        print("Warning: Docker Compose not found. You'll need it for easy multi-service deployment.")
    
    return True

def setup_virtual_environment():
    """Create and activate virtual environment."""
    print("\nSetting up virtual environment...")
    
    if not run_command("python -m venv venv", "Creating virtual environment"):
        return False
    
    # Activation command varies by OS
    if os.name == 'nt':  # Windows
        activate_cmd = r"venv\Scripts\activate && "
    else:  # Unix-like
        activate_cmd = "source venv/bin/activate && "
    
    if not run_command(f"{activate_cmd}pip install --upgrade pip", "Upgrading pip"):
        return False
    
    if not run_command(f"{activate_cmd}pip install -r requirements.txt", "Installing dependencies"):
        return False
    
    print("✓ Virtual environment created and dependencies installed")
    return True

def setup_configuration():
    """Set up configuration files."""
    print("\nSetting up configuration...")
    
    # Copy environment template
    if not os.path.exists(".env"):
        shutil.copy("config.env.example", ".env")
        print("✓ Created .env file from template")
        print("⚠️  Please edit .env file with your AWS credentials and configuration")
    else:
        print("✓ .env file already exists")
    
    return True

def check_services():
    """Check if required services are available."""
    print("\nChecking services...")
    
    # Try to connect to Elasticsearch if it's running
    try:
        import requests
        response = requests.get("http://localhost:9200", timeout=5)
        if response.status_code == 200:
            print("✓ Elasticsearch is running on localhost:9200")
        else:
            print("⚠️  Elasticsearch responded with status:", response.status_code)
    except:
        print("⚠️  Elasticsearch not running on localhost:9200")
        print("   You can start it with: docker-compose up elasticsearch -d")
    
    return True

def create_sample_documents():
    """Create sample documents for testing."""
    print("\nCreating sample documents...")
    
    sample_dir = Path("sample_documents")
    sample_dir.mkdir(exist_ok=True)
    
    # Create sample text file
    with open(sample_dir / "sample.txt", "w") as f:
        f.write("This is a sample text document for testing the document search application.")
    
    # Create sample CSV file
    with open(sample_dir / "sample.csv", "w") as f:
        f.write("Name,Email,Department\n")
        f.write("John Doe,john@example.com,Engineering\n")
        f.write("Jane Smith,jane@example.com,Marketing\n")
    
    print(f"✓ Created sample documents in {sample_dir}")
    print("   You can upload these to your S3 bucket for testing")
    
    return True

def main():
    """Main setup function."""
    print("Document Search Application Setup")
    print("=" * 40)
    
    if not check_requirements():
        sys.exit(1)
    
    if not setup_virtual_environment():
        print("Failed to set up virtual environment")
        sys.exit(1)
    
    if not setup_configuration():
        print("Failed to set up configuration")
        sys.exit(1)
    
    check_services()
    create_sample_documents()
    
    print("\n" + "=" * 40)
    print("Setup Complete!")
    print("\nNext steps:")
    print("1. Edit .env file with your AWS credentials")
    print("2. Start Elasticsearch: docker-compose up elasticsearch -d")
    print("3. Start the API: python app.py")
    print("4. Test the CLI: python cli.py status")
    print("5. Upload documents to your S3 bucket")
    print("6. Process documents: python cli.py process")
    print("7. Search documents: python cli.py search 'your query'")
    
    if os.name == 'nt':  # Windows
        print("\nTo activate the virtual environment:")
        print("   venv\\Scripts\\activate")
    else:  # Unix-like
        print("\nTo activate the virtual environment:")
        print("   source venv/bin/activate")

if __name__ == "__main__":
    main() 