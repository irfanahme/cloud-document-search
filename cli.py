"""CLI entry point for Document Search application."""

import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.cli.client import cli

if __name__ == '__main__':
    cli() 